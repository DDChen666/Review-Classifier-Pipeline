#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
2-3.數據標註.py（修復＋自動校驗回補循環版，google-genai）

功能總覽：
- 讀取 output/ 下最新的 unlabeled_reviews_*.json，使用 gemini-2.5-flash 批次分類（結構化輸出）
- 產生 labeled_reviews_*.json
- 隨後自動讀取「最新生成的資料集檔案」（預設為剛輸出那個），執行：
    校驗 -> 若有錯誤則列印 10 筆 -> 僅重跑錯誤樣本給 Gemini -> 修復資料集 -> 迴圈直到全數合法
- 修復後輸出 <原檔名>_fixed.json

安裝：
  pip install -U google-genai python-dotenv pydantic

環境變數：
  .env 內設 GEMINI_API_KEY=你的key  （或改用 GOOGLE_API_KEY）
"""

from __future__ import annotations
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from dotenv import load_dotenv

# 新版 SDK
from google import genai
from google.genai import types

from pydantic import BaseModel
from enum import Enum


# ==============================
# 基本設定
# ==============================
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("請在 .env 設定 GEMINI_API_KEY 或 GOOGLE_API_KEY")

MODEL_NAME = "gemini-2.5-flash"
BATCH_SIZE = 100
MAX_RETRIES = 5
RETRY_DELAY_SEC = 30

# 校驗＋回補的最大循環回合數（防止極端情況無限迴圈）
VALIDATE_MAX_ROUNDS = 8


# ==============================
# 正確的結構化輸出 Schema（6 × 4）
# ==============================
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


class LabelPair(BaseModel):
    primary: PrimaryCategory
    secondary: SecondaryCategory


# 允許值集合（大小寫嚴格）
PRIMARY_ALLOW = {e.value for e in PrimaryCategory}
SECONDARY_ALLOW = {e.value for e in SecondaryCategory}

# 同義詞/寫法正規化映射（模型若輸出非白名單，先嘗試映射；最後仍有保底）
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


def _normalize_enum(value: Any, allow: set, mapping: Dict[str, str], fallback: str) -> str:
    """
    把模型輸出的自由文字，正規化為白名單中的枚舉字面值。
    嚴格大小寫；若非白名單則嘗試映射；否則回退 fallback。
    """
    if isinstance(value, str):
        v = value.strip()
        if v in allow:
            return v
        key = v.upper().replace("-", "_").replace(" ", "").replace(".", "")
        if key in mapping:
            mapped = mapping[key]
            return mapped if mapped in allow else fallback
    return fallback


# ==============================
# 標註器
# ==============================
class GeminiAnnotator:
    """
    使用 google-genai 完成分類，強制 JSON 結構輸出。
    僅要求回傳 [ { "primary": "...", "secondary": "..." }, ... ]
    """
    def __init__(self, api_key: str, model_name: str = MODEL_NAME):
        self.client = genai.Client(api_key=api_key)
        self.model = model_name

        # 系統說明：固定輸出格式＋決策規則
        self.system_instruction = (
            "You classify mobile-banking user reviews using TWO orthogonal labels.\n"
            "Output strictly as a JSON array of objects, each with ONLY these keys:\n"
            '  {"primary": <one of ["BUG","UI/UX","FEATURE_REQUEST","PERFORMANCE","POSITIVE","INVALID"]>, '
            '   "secondary": <one of ["ACCOUNT","TRANSACTION","CREDIT_CARD","GENERAL"]>}\n'
            "Do NOT include text, explanations, or extra fields.\n\n"
            "Decision rules:\n"
            "1) Primary is the NATURE of feedback (Why). Pick ONE of: BUG, UI/UX, PERFORMANCE, FEATURE_REQUEST, POSITIVE, INVALID.\n"
            "   Severity priority when mixed: BUG > UI/UX > PERFORMANCE > FEATURE_REQUEST.\n"
            "2) Secondary is the FEATURE AREA (What/Where). Pick ONE of: ACCOUNT, TRANSACTION, CREDIT_CARD, GENERAL.\n"
            "3) Primary & Secondary are independent; not hierarchical.\n"
            "4) If ambiguous, use INVALID (primary) and GENERAL (secondary).\n"
        )

        self.config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.1,
            top_p=0.9,
            max_output_tokens=60000,
            response_mime_type="application/json",
            response_schema=list[LabelPair],  # 嚴格要求 [LabelPair]
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
    @staticmethod
    def _clean_json_text(text: str) -> str:
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

    def _convert_to_label_dict(self, item: Any) -> Dict[str, str] | None:
        if item is None:
            return None

        if isinstance(item, LabelPair):
            data: Dict[str, Any] = item.model_dump()
        elif isinstance(item, BaseModel):
            data = item.model_dump()
        elif isinstance(item, dict):
            data = item
        else:
            return None

        primary = data.get("primary")
        secondary = data.get("secondary")

        if primary is None:
            for key in ("primary_label", "primaryLabel", "primaryCategory", "primary_category"):
                if key in data:
                    primary = data[key]
                    break

        if secondary is None:
            for key in ("secondary_label", "secondaryLabel", "secondaryCategory", "secondary_category"):
                if key in data:
                    secondary = data[key]
                    break

        if isinstance(primary, Enum):
            primary = primary.value
        if isinstance(secondary, Enum):
            secondary = secondary.value

        result: Dict[str, str] = {}
        if primary is not None:
            result["primary"] = str(primary)
        if secondary is not None:
            result["secondary"] = str(secondary)

        if not result:
            return None
        return result

    def _coerce_label_items(self, data: Any) -> List[dict] | None:
        if data is None:
            return None

        if isinstance(data, str):
            clean = self._clean_json_text(data)
            try:
                data = json.loads(clean)
            except json.JSONDecodeError:
                print("錯誤：回應不是合法 JSON。原始回應（前 500 字）：", clean[:500])
                return None

        items: List[dict] = []
        if isinstance(data, list):
            for item in data:
                converted = self._convert_to_label_dict(item)
                if converted:
                    items.append(converted)
        elif isinstance(data, dict):
            found_list = False
            for key in ("labels", "items", "data", "results", "output", "predictions"):
                value = data.get(key)
                if isinstance(value, list):
                    found_list = True
                    for item in value:
                        converted = self._convert_to_label_dict(item)
                        if converted:
                            items.append(converted)
            if not found_list:
                converted = self._convert_to_label_dict(data)
                if converted:
                    items.append(converted)
        else:
            converted = self._convert_to_label_dict(data)
            if converted:
                items.append(converted)

        return items or None

    def _extract_json_payload(self, resp: Any) -> Optional[str]:
        if not resp:
            return None

        text_attr = getattr(resp, "text", None)
        if text_attr:
            stripped = self._clean_json_text(str(text_attr))
            if stripped:
                return stripped

        def iter_parts():
            response_parts = getattr(resp, "parts", None) or []
            for part in response_parts:
                yield part
            candidates = getattr(resp, "candidates", None) or []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                if content:
                    for part in getattr(content, "parts", None) or []:
                        yield part

        for part in iter_parts():
            text_part = getattr(part, "text", None)
            if text_part:
                stripped = self._clean_json_text(str(text_part))
                if stripped:
                    return stripped

            func_call = getattr(part, "function_call", None)
            if func_call:
                args = getattr(func_call, "args", None) or {}
                if isinstance(args, dict):
                    for key in ("json", "response", "output", "data", "labels", "result"):
                        if key in args:
                            value = args[key]
                            if isinstance(value, str):
                                cleaned = self._clean_json_text(value)
                                if cleaned:
                                    return cleaned
                            else:
                                try:
                                    return json.dumps(value, ensure_ascii=False)
                                except TypeError:
                                    continue

            func_response = getattr(part, "function_response", None)
            if func_response:
                response_payload = getattr(func_response, "response", None)
                if response_payload:
                    try:
                        return json.dumps(response_payload, ensure_ascii=False)
                    except TypeError:
                        pass

        return None

    def _log_response_debug(self, resp: Any) -> None:
        print("警告：未獲取到有效回應。")
        if not resp:
            return
        try:
            print("  - prompt_feedback:", getattr(resp, "prompt_feedback", None))
            candidates = getattr(resp, "candidates", None) or []
            print("  - candidates:", len(candidates))
            raw_text = getattr(resp, "text", None)
            if raw_text:
                preview = self._clean_json_text(str(raw_text))[:200]
                if preview:
                    print("  - raw_text_preview:", preview)
            for idx, candidate in enumerate(candidates[:2]):
                finish_reason = getattr(candidate, "finish_reason", None)
                finish_message = getattr(candidate, "finish_message", None)
                message = f"    candidate[{idx}] finish_reason={finish_reason}, finish_message={finish_message}"
                snippets: List[str] = []
                content = getattr(candidate, "content", None)
                if content:
                    for part in getattr(content, "parts", None) or []:
                        text_part = getattr(part, "text", None)
                        if text_part:
                            snippet = self._clean_json_text(str(text_part)).replace("\n", " ")
                            if snippet:
                                snippets.append(snippet[:120])
                        func_call = getattr(part, "function_call", None)
                        if func_call and getattr(func_call, "args", None):
                            try:
                                snippets.append(f"function_call args keys: {sorted(func_call.args.keys())}")
                            except Exception:
                                pass
                if snippets:
                    message += f", sample={snippets[0]}"
                print(message)
        except Exception:
            pass

    def _call_model_once(self, texts: List[str]) -> List[dict]:
        """
        單次呼叫模型。輸入多筆 text，輸出為 List[{"primary":..., "secondary":...}].
        """
        payload = {"reviews": [{"text": t} for t in texts]}
        prompt = (
            "Classify the following reviews.\n"
            "Return ONLY the JSON array of objects with keys {primary, secondary} as per schema.\n"
            f"Input:\n{json.dumps(payload, ensure_ascii=False)}"
        )

        resp = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self.config,
        )

        parsed = self._coerce_label_items(getattr(resp, "parsed", None))
        if parsed:
            return parsed

        payload_text = self._extract_json_payload(resp)
        if payload_text:
            parsed_from_text = self._coerce_label_items(payload_text)
            if parsed_from_text:
                return parsed_from_text

        self._log_response_debug(resp)
        return []


    def _post_sanitize(self, raw_items: List[dict]) -> List[dict]:
        """
        白名單與同義正規化，確保最終落地是合法枚舉。
        """
        sanitized: List[dict] = []
        for it in raw_items:
            p = _normalize_enum(it.get("primary"), PRIMARY_ALLOW, PRIMARY_MAP, fallback="INVALID")
            s = _normalize_enum(it.get("secondary"), SECONDARY_ALLOW, SECONDARY_MAP, fallback="GENERAL")
            sanitized.append({"primary": p, "secondary": s})
        return sanitized


    def annotate_batch(self, reviews: List[dict]) -> List[dict]:
        """
        將一批 review dict（至少含 'text'）送模型，回傳標註後的列表。
        具備重試、與標籤正規化。
        """
        texts = [str(r.get("text", "")) for r in reviews]
        attempt = 0
        while attempt < MAX_RETRIES:
            try:
                out = self._call_model_once(texts)
                if out and isinstance(out, list):
                    out = self._post_sanitize(out)
                    n = min(len(out), len(reviews))
                    merged: List[dict] = []
                    for i in range(n):
                        item = {
                            **reviews[i],
                            "primary": out[i].get("primary"),
                            "secondary": out[i].get("secondary"),
                        }
                        item["text"] = reviews[i].get("text", "")
                        merged.append(item)
                    if len(out) != len(reviews):
                        print(f"警告：模型回傳 {len(out)} 筆與輸入 {len(reviews)} 筆不符，使用預設標籤補齊。")
                    for i in range(n, len(reviews)):
                        merged.append({
                            **reviews[i],
                            "primary": "INVALID",
                            "secondary": "GENERAL",
                            "text": reviews[i].get("text", ""),
                        })
                    if merged:
                        return merged
            except Exception as e:
                print(f"第 {attempt + 1} 次呼叫 API 失敗: {e}")
                if attempt + 1 >= MAX_RETRIES:
                    break

            attempt += 1
            print(f"重試中（{attempt}/{MAX_RETRIES}）…")
            time.sleep(RETRY_DELAY_SEC)

        print("此批次標註失敗，保留原始資料。")
        fallback = []
        for r in reviews:
            fallback.append({
                **r,
                "primary": "INVALID",
                "secondary": "GENERAL",
                "text": r.get("text", "")
            })
        return fallback


# ==============================
# I/O 工具
# ==============================
def find_latest_unlabeled_file(output_dir: Path) -> Path | None:
    files = list(output_dir.glob("unlabeled_reviews_*.json"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def find_latest_labeled_file(output_dir: Path) -> Path | None:
    files = list(output_dir.glob("labeled_reviews_*.json"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def load_reviews(path: Path) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_reviews(data: List[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==============================
# 校驗與自動回補
# ==============================
def _is_valid_label(value: Any, allow: set) -> bool:
    return isinstance(value, str) and value in allow


def validate_reviews(reviews: List[dict]) -> Tuple[List[int], List[dict]]:
    """
    逐一校驗 primary / secondary 是否為合法白名單。
    回傳：
      invalid_indices: List[int]  -> 不合法樣本在 reviews 的索引
      diagnostics:     List[dict] -> 每筆錯誤的理由（最多取前若干筆時可印）
    """
    invalid_indices: List[int] = []
    diagnostics: List[dict] = []
    for i, r in enumerate(reviews):
        p = r.get("primary")
        s = r.get("secondary")
        errs = []
        if not _is_valid_label(p, PRIMARY_ALLOW):
            errs.append(f"primary 非法: {p!r}")
        if not _is_valid_label(s, SECONDARY_ALLOW):
            errs.append(f"secondary 非法: {s!r}")
        if errs:
            invalid_indices.append(i)
            text_preview = str(r.get("text", ""))[:80]
            diagnostics.append({
                "index": i,
                "primary": p,
                "secondary": s,
                "reasons": errs,
                "text_preview": (text_preview + ("..." if len(str(r.get("text",""))) > 80 else "")),
            })
    return invalid_indices, diagnostics


def fix_dataset_loop(
    reviews: List[dict],
    annotator: GeminiAnnotator,
    batch_size: int = BATCH_SIZE,
    max_rounds: int = VALIDATE_MAX_ROUNDS,
) -> List[dict]:
    """
    校驗 -> 修補 -> 迴圈直到全數合法或達到 max_rounds。
    僅針對不合法樣本呼叫模型，其他樣本不動。
    """
    round_id = 1
    while round_id <= max_rounds:
        invalid_indices, diagnostics = validate_reviews(reviews)
        invalid_count = len(invalid_indices)
        print(f"\n[校驗回合 {round_id}] 不合法樣本數：{invalid_count}")

        if invalid_count == 0:
            print("✔ 全部標籤均合法。")
            break

        # 列印前 10 筆錯誤樣本
        print("  ├─ 錯誤示例（最多 10 筆）：")
        for d in diagnostics[:10]:
            print(f"    - idx={d['index']}, primary={d['primary']}, secondary={d['secondary']}, reasons={d['reasons']}")
            print(f"      text: {d['text_preview']}")

        # 僅抽取不合法樣本，分批送模型重跑
        total = invalid_count
        for i in range(0, total, batch_size):
            batch_positions = invalid_indices[i:i + batch_size]
            batch = [reviews[pos] for pos in batch_positions]

            # 如果 text 缺失，直接用 INVALID/GENERAL 回填，避免卡住
            for b in batch:
                if not b.get("text"):
                    b["primary"] = "INVALID"
                    b["secondary"] = "GENERAL"

            labeled = annotator.annotate_batch(batch)
            # 回填到原陣列對應位置
            for rel_idx, pos in enumerate(batch_positions):
                if rel_idx < len(labeled):
                    reviews[pos]["primary"] = labeled[rel_idx].get("primary", "INVALID")
                    reviews[pos]["secondary"] = labeled[rel_idx].get("secondary", "GENERAL")

        round_id += 1

    if round_id > max_rounds:
        print("\n⚠ 已達到最大修補回合數，資料仍可能含有不合法標籤。")

    return reviews


# ==============================
# 主流程
# ==============================
def main() -> None:
    print("=== 評論數據標註工具（含校驗回補）===")
    print(f"使用模型: {MODEL_NAME}, 批次大小: {BATCH_SIZE}")

    script_dir = Path(__file__).parent
    out_dir = (script_dir / "output")
    out_dir.mkdir(exist_ok=True, parents=True)

    # Step 1: 若有未標註檔，先執行標註
    in_file = find_latest_unlabeled_file(out_dir)
    latest_labeled_before = find_latest_labeled_file(out_dir)

    produced_file: Path | None = None
    if in_file:
        print(f"\n[標註] 找到未標註文件：{in_file.name}")
        reviews = load_reviews(in_file)
        print(f"[標註] 讀入 {len(reviews)} 條評論；僅處理尚未標註的樣本")

        pending = [r for r in reviews if not r.get("primary")]
        done = [r for r in reviews if r.get("primary")]

        annotator = GeminiAnnotator(API_KEY)
        labeled_all: List[dict] = list(done)

        total = len(pending)
        print(f"[標註] 未標註樣本數：{total}")
        for i in range(0, total, BATCH_SIZE):
            batch = pending[i:i + BATCH_SIZE]
            print("-" * 20)
            print(f"[標註] 批次 {i//BATCH_SIZE + 1}/{(total + BATCH_SIZE - 1)//BATCH_SIZE}（{len(batch)} 條）")
            labeled = annotator.annotate_batch(batch)

            # 預覽
            print("  - 批次結果預覽 (前 10 筆):")
            for item in labeled[:10]:
                text_preview = item.get("text", "")
                if len(text_preview) > 50:
                    text_preview = text_preview[:50] + "..."
                print(f"    - Text: '{text_preview}' -> P={item.get('primary')}, S={item.get('secondary')}")

            labeled_all.extend(labeled)
            time.sleep(0.3)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = out_dir / f"labeled_reviews_{ts}.json"
        save_reviews(labeled_all, out_file)
        produced_file = out_file
        print(f"\n[標註] 完成，共 {len(labeled_all)} 條，已輸出：{out_file.name}")
    else:
        print("\n[標註] 沒有發現未標註檔，跳過標註步驟。")

    # Step 2: 自動校驗回補 —— 讀取「最新生成的資料集檔案」
    # 以「本次剛輸出」為主；若本次無輸出，取現存最新 labeled 檔
    target_file = produced_file if produced_file else find_latest_labeled_file(out_dir)
    if not target_file:
        # 沒有任何 labeled 檔
        print("\n[校驗] 找不到 labeled_reviews_*.json，略過校驗。")
        return

    print(f"\n[校驗] 讀取最新生成的資料集：{target_file.name}")
    data = load_reviews(target_file)

    # 校驗與修補循環
    annotator = GeminiAnnotator(API_KEY)
    fixed = fix_dataset_loop(data, annotator, batch_size=BATCH_SIZE, max_rounds=VALIDATE_MAX_ROUNDS)

    # 最終再做一次嚴格校驗，若仍有錯誤會告知
    invalid_indices, diagnostics = validate_reviews(fixed)
    if invalid_indices:
        print(f"\n⚠ 修補後仍有 {len(invalid_indices)} 筆不合法標籤。將仍輸出修補檔供後續人工檢查。")
        print("  ├─ 錯誤示例（最多 10 筆）：")
        for d in diagnostics[:10]:
            print(f"    - idx={d['index']}, primary={d['primary']}, secondary={d['secondary']}, reasons={d['reasons']}")
            print(f"      text: {d['text_preview']}")
    else:
        print("\n✔ 修補後全部標籤均合法。")

    # 以「<原檔>_fixed.json」輸出
    fixed_path = target_file.with_name(target_file.stem + "_fixed.json")
    save_reviews(fixed, fixed_path)
    print(f"\n[校驗] 修復後資料已輸出：{fixed_path.name}")
    print("\n=== 全流程完成 ===")


if __name__ == "__main__":
    main()
