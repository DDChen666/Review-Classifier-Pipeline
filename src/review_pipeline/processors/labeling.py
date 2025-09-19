
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from ..config import LabelingConfig
from ..labelers.base import BaseLabeler
from ..labelers.gemini import GeminiLabeler


@dataclass
class LabelingWorkflow:
    config: LabelingConfig
    logger: logging.Logger = logging.getLogger("review_pipeline.processors.labeling")

    def __post_init__(self) -> None:
        if self.config.provider == "gemini":
            self.labeler: BaseLabeler = GeminiLabeler(self.config.gemini)
        else:  # pragma: no cover - defensive
            raise ValueError(f"Unsupported labeler provider: {self.config.provider}")

    def run(
        self,
        unlabeled_path: Path,
        labeled_output: Path,
        fixed_output: Optional[Path] = None,
        run_validation: bool = True,
    ) -> dict:
        data = self._load_json(unlabeled_path)
        self.logger.info("Loaded %s records for labeling from %s", len(data), unlabeled_path)

        pending = [record for record in data if not record.get("primary")]
        completed = [record for record in data if record.get("primary")]

        if pending:
            self.logger.info("Annotating %s previously unlabeled records", len(pending))
            annotated = self.labeler.annotate(pending)
            combined = completed + annotated
        else:
            self.logger.info("No unlabeled records found; skipping annotation step")
            combined = data

        labeled_output = labeled_output.resolve()
        labeled_output.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(combined, labeled_output)
        self.logger.info("Labeled dataset saved to %s", labeled_output)

        fixed_records: Optional[List[dict]] = None
        if run_validation and combined:
            fixed_records = self._run_validation_loop([dict(item) for item in combined])

        results = {"labeled_path": labeled_output, "fixed_path": None}
        if fixed_records and fixed_output:
            fixed_output = fixed_output.resolve()
            fixed_output.parent.mkdir(parents=True, exist_ok=True)
            self._write_json(fixed_records, fixed_output)
            self.logger.info("Validation-corrected dataset saved to %s", fixed_output)
            results["fixed_path"] = fixed_output
        elif fixed_records and not fixed_output:
            self.logger.debug("Validation corrections computed but no output path provided; skipping write.")

        return results

    def _run_validation_loop(self, records: List[dict]) -> List[dict]:
        max_rounds = getattr(self.config.gemini, "validate_max_rounds", 1)
        batch_size = getattr(self.config.gemini, "batch_size", 100)

        for round_id in range(1, max_rounds + 1):
            diagnostics = self.labeler.validate(records)
            if not diagnostics:
                self.logger.info("Validation round %s: all labels valid", round_id)
                return records

            self.logger.warning(
                "Validation round %s: %s invalid records detected", round_id, len(diagnostics)
            )
            for diag in diagnostics[:10]:
                self.logger.debug(
                    "Invalid record idx=%s primary=%s secondary=%s reasons=%s text=%s",
                    diag["index"],
                    diag.get("primary"),
                    diag.get("secondary"),
                    diag.get("reasons"),
                    diag.get("text_preview"),
                )

            indices = [d["index"] for d in diagnostics]
            for start in range(0, len(indices), batch_size):
                chunk = indices[start : start + batch_size]
                batch = [records[idx] for idx in chunk]
                for item in batch:
                    if not item.get("text"):
                        fallback = item.get("content") or item.get("review") or ""
                        item["text"] = fallback
                        if not fallback:
                            item["primary"] = "INVALID"
                            item["secondary"] = "GENERAL"
                relabeled = self.labeler.annotate_batch(batch)
                for offset, idx in enumerate(chunk):
                    if offset < len(relabeled):
                        records[idx]["primary"] = relabeled[offset].get("primary", "INVALID")
                        records[idx]["secondary"] = relabeled[offset].get("secondary", "GENERAL")
            self.logger.info("Validation round %s completed", round_id)

        self.logger.warning(
            "Reached maximum validation rounds (%s); dataset may still contain invalid labels.",
            max_rounds,
        )
        return records

    @staticmethod
    def _load_json(path: Path) -> List[dict]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(data: Sequence[dict], path: Path) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(list(data), handle, ensure_ascii=False, indent=2)
