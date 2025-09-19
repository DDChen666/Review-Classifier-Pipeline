
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Sequence, Tuple

from dotenv import load_dotenv
from textwrap import dedent
from google import genai
from google.genai import types
from pydantic import BaseModel

from ..config import GeminiConfig
from .base import BaseLabeler


class PrimaryCategory(str, Enum):
    BUG = "BUG"
    UI_UX = "UI/UX"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    PERFORMANCE = "PERFORMANCE"
    POSITIVE = "POSITIVE"
    INVALID = "INVALID"


class SecondaryCategory(str, Enum):
    ACCOUNT = "ACCOUNT"
    TRANSACTION = "TRANSACTION"
    CREDIT_CARD = "CREDIT_CARD"
    GENERAL = "GENERAL"


PRIMARY_ALLOW = {e.value for e in PrimaryCategory}
SECONDARY_ALLOW = {e.value for e in SecondaryCategory}

PRIMARY_MAP = {
    "UX": "UI/UX",
    "UI": "UI/UX",
    "UIUX": "UI/UX",
    "REQUEST": "FEATURE_REQUEST",
    "FEATURE": "FEATURE_REQUEST",
    "SLOW": "PERFORMANCE",
    "LAG": "PERFORMANCE",
    "CRASH": "BUG",
    "ERROR": "BUG",
    "BUG_REPORT": "BUG",
    "PRAISE": "POSITIVE",
    "POSITIVE_REVIEW": "POSITIVE",
    "UNKNOWN": "INVALID",
    "N/A": "INVALID",
    "SPAM": "INVALID",
}

SECONDARY_MAP = {
    "LOGIN": "ACCOUNT",
    "AUTH": "ACCOUNT",
    "ACCOUNT_INQUIRY": "ACCOUNT",
    "HISTORY": "ACCOUNT",
    "BALANCE": "ACCOUNT",
    "PAYMENT": "TRANSACTION",
    "PAY": "TRANSACTION",
    "TRANSFER": "TRANSACTION",
    "WIRE": "TRANSACTION",
    "REMITTANCE": "TRANSACTION",
    "QR": "TRANSACTION",
    "CARD": "CREDIT_CARD",
    "CREDITCARD": "CREDIT_CARD",
    "CC": "CREDIT_CARD",
    "STATEMENT": "CREDIT_CARD",
    "BILL": "CREDIT_CARD",
    "REWARD": "CREDIT_CARD",
    "APP": "GENERAL",
    "HOMEPAGE": "GENERAL",
    "SETTINGS": "GENERAL",
    "NOTIFICATION": "GENERAL",
}


class LabelPair(BaseModel):
    primary: PrimaryCategory
    secondary: SecondaryCategory


@dataclass
class GeminiLabeler(BaseLabeler):
    config: GeminiConfig
    logger: logging.Logger = logging.getLogger("review_pipeline.labelers.gemini")

    def __post_init__(self) -> None:
        load_dotenv()
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise ValueError(
                f"Environment variable {self.config.api_key_env} is not set; cannot initialise Gemini labeler."
            )

        self.client = genai.Client(api_key=api_key)
        self.system_instruction = dedent("""
            You classify mobile-banking user reviews using TWO orthogonal labels.
            Output strictly as a JSON array of objects, each with ONLY these keys:
              {"primary": <one of ["BUG","UI/UX","FEATURE_REQUEST","PERFORMANCE","POSITIVE","INVALID"]>, "secondary": <one of ["ACCOUNT","TRANSACTION","CREDIT_CARD","GENERAL"]>}
            Do NOT include text, explanations, or extra fields.

            Decision rules:
            1) Primary is the NATURE of feedback (Why). Pick ONE of: BUG, UI/UX, PERFORMANCE, FEATURE_REQUEST, POSITIVE, INVALID.
               Severity priority when mixed: BUG > UI/UX > PERFORMANCE > FEATURE_REQUEST.
            2) Secondary is the FEATURE AREA (What/Where). Pick ONE of: ACCOUNT, TRANSACTION, CREDIT_CARD, GENERAL.
            3) Primary & Secondary are independent; not hierarchical.
            4) If ambiguous, use INVALID (primary) and GENERAL (secondary).
        """).strip()

        self.generate_config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.1,
            top_p=0.9,
            max_output_tokens=60000,
            response_mime_type="application/json",
            response_schema=list[LabelPair],
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def annotate(self, records: Sequence[dict]) -> List[dict]:
        labelled: List[dict] = []
        for start in range(0, len(records), self.config.batch_size):
            batch = list(records[start : start + self.config.batch_size])
            result = self.annotate_batch(batch)
            labelled.extend(result)
            time.sleep(0.3)
        return labelled

    def annotate_batch(self, records: Sequence[dict]) -> List[dict]:
        texts = [str(r.get("text", "")) for r in records]
        attempt = 0
        while attempt <= self.config.max_retries:
            try:
                raw = self._call_model_once(texts)
                if raw:
                    labelled = self._post_sanitise(raw)
                    merged: List[dict] = []
                    limit = min(len(labelled), len(records))
                    for idx in range(limit):
                        merged.append(
                            {
                                **records[idx],
                                "text": records[idx].get("text", ""),
                                "primary": labelled[idx].get("primary", "INVALID"),
                                "secondary": labelled[idx].get("secondary", "GENERAL"),
                            }
                        )
                    for idx in range(limit, len(records)):
                        merged.append(
                            {
                                **records[idx],
                                "text": records[idx].get("text", ""),
                                "primary": "INVALID",
                                "secondary": "GENERAL",
                            }
                        )
                    return merged
            except Exception as exc:  # pragma: no cover - network errors
                self.logger.warning(
                    "Gemini annotate attempt %s/%s failed: %s",
                    attempt + 1,
                    self.config.max_retries + 1,
                    exc,
                )
            attempt += 1
            if attempt <= self.config.max_retries:
                time.sleep(self.config.retry_delay_sec)

        self.logger.error("Gemini annotate failed; returning INVALID placeholders.")
        return [
            {**record, "primary": "INVALID", "secondary": "GENERAL", "text": record.get("text", "")}
            for record in records
        ]

    def validate(self, records: Sequence[dict]) -> List[dict]:
        invalid: List[dict] = []
        for idx, record in enumerate(records):
            primary = record.get("primary")
            secondary = record.get("secondary")
            issues = []
            if not self._is_valid_label(primary, PRIMARY_ALLOW):
                issues.append(f"primary invalid: {primary!r}")
            if not self._is_valid_label(secondary, SECONDARY_ALLOW):
                issues.append(f"secondary invalid: {secondary!r}")
            if issues:
                preview = str(record.get("text", ""))
                if len(preview) > 80:
                    preview = preview[:80] + "..."
                invalid.append(
                    {
                        "index": idx,
                        "reasons": issues,
                        "primary": primary,
                        "secondary": secondary,
                        "text_preview": preview,
                    }
                )
        return invalid

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _call_model_once(self, texts: Sequence[str]) -> List[dict]:
        payload = {"reviews": [{"text": t} for t in texts]}
        prompt = dedent(
            f"""
            Classify the following reviews.
            Return ONLY the JSON array of objects with keys {primary, secondary} as per schema.
            Input:
            {json.dumps(payload, ensure_ascii=False)}
            """
        ).strip()

        response = self.client.models.generate_content(
            model=self.config.model,
            contents=prompt,
            config=self.generate_config,
        )

        parsed = self._coerce_label_items(getattr(response, "parsed", None))
        if parsed:
            return parsed

        payload_text = self._extract_json_payload(response)
        if payload_text:
            parsed_from_text = self._coerce_label_items(payload_text)
            if parsed_from_text:
                return parsed_from_text

        self._log_debug_response(response)
        return []

    @staticmethod
    def _is_valid_label(value: Any, allow: set) -> bool:
        return isinstance(value, str) and value in allow

    def _post_sanitise(self, raw_items: List[dict]) -> List[dict]:
        cleaned: List[dict] = []
        for item in raw_items:
            primary = self._normalize_enum(item.get("primary"), PRIMARY_ALLOW, PRIMARY_MAP, "INVALID")
            secondary = self._normalize_enum(item.get("secondary"), SECONDARY_ALLOW, SECONDARY_MAP, "GENERAL")
            cleaned.append({"primary": primary, "secondary": secondary})
        return cleaned

    def _normalize_enum(
        self,
        value: Any,
        allow: set,
        mapping: Dict[str, str],
        fallback: str,
    ) -> str:
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, str):
            trimmed = value.strip().upper().replace(" ", "_")
            trimmed = mapping.get(trimmed, trimmed)
            if trimmed in allow:
                return trimmed
        return fallback

    def _coerce_label_items(self, data: Any) -> List[dict] | None:
        if data is None:
            return None
        if isinstance(data, list):
            results: List[dict] = []
            for item in data:
                converted = self._convert_to_label_dict(item)
                if converted:
                    results.append(converted)
            return results
        if isinstance(data, str):
            return self._coerce_label_items(self._clean_response_text(data))
        return None

    def _convert_to_label_dict(self, item: Any) -> Dict[str, str] | None:
        if item is None:
            return None
        if isinstance(item, LabelPair):
            payload: Dict[str, Any] = item.model_dump()
        elif isinstance(item, BaseModel):
            payload = item.model_dump()
        elif isinstance(item, dict):
            payload = item
        else:
            return None

        primary = payload.get("primary")
        secondary = payload.get("secondary")

        if isinstance(primary, Enum):
            primary = primary.value
        if isinstance(secondary, Enum):
            secondary = secondary.value

        if primary is None:
            for key in ("primary_label", "primaryLabel", "primaryCategory", "primary_category"):
                if key in payload:
                    primary = payload[key]
                    break
        if secondary is None:
            for key in ("secondary_label", "secondaryLabel", "secondaryCategory", "secondary_category"):
                if key in payload:
                    secondary = payload[key]
                    break

        result: Dict[str, str] = {}
        if primary is not None:
            result["primary"] = str(primary)
        if secondary is not None:
            result["secondary"] = str(secondary)
        return result or None

    def _clean_response_text(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines:
                lines = lines[1:]
                while lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
            stripped = "\n".join(lines).strip()

        if stripped.endswith(";"):
            stripped = stripped[:-1].rstrip()
        return stripped

    def _extract_json_payload(self, response: Any) -> str | None:
        candidates = []
        if hasattr(response, "text") and response.text:
            candidates.append(response.text)
        if hasattr(response, "candidates"):
            for cand in response.candidates or []:
                if getattr(cand, "content", None):
                    for part in cand.content.parts or []:
                        text = getattr(part, "text", None)
                        if text:
                            candidates.append(text)
        for candidate in candidates:
            cleaned = self._clean_response_text(candidate)
            if cleaned:
                return cleaned
        return None

    def _log_debug_response(self, response: Any) -> None:
        try:
            payload = getattr(response, "text", None) or getattr(response, "candidates", None)
            self.logger.debug("Gemini raw response: %s", payload)
        except Exception:  # pragma: no cover - defensive
            self.logger.debug("Gemini raw response could not be logged.")