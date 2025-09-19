
from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..config import CleaningConfig


FULLWIDTH_CHARS = (
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～　"
)
HALFWIDTH_CHARS = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~ "
)
TRANSLATION_TABLE = str.maketrans(FULLWIDTH_CHARS, HALFWIDTH_CHARS)

EMOJI_REGEX = re.compile(
    "[😀-🙏]"
    "|[🌀-🗿]"
    "|[🚀-🛿]"
    "|[🇠-🇿]"
    "|[🤀-🧿]"
    "|[🨀-🩯]"
    "|[🩰-🫿]"
    "|[☀-⛿]"
    "|[✀-➿]"
    "|[🀄🃏]"
    "|[🅰-🉑]"
    "|[︀-️]"
    "|[ -⁯]",
    flags=re.UNICODE,
)


@dataclass
class LabelingDatasetPreparer:
    config: CleaningConfig
    logger: logging.Logger = logging.getLogger("review_pipeline.processors.cleaning")

    def prepare(self, merged_csv: Path, output_json: Path) -> Path:
        df = pd.read_csv(merged_csv)
        self.logger.info("Loaded %s merged reviews from %s", len(df), merged_csv)

        prepared = []
        for _, row in df.iterrows():
            text = str(row.get("content", "")).strip()
            if not text:
                continue
            cleaned = self.clean_text(text)
            if not self._passes_length_checks(cleaned):
                continue
            prepared.append({"text": cleaned, "primary": "", "secondary": ""})

        output_json.parent.mkdir(parents=True, exist_ok=True)
        with output_json.open("w", encoding="utf-8") as handle:
            json.dump(prepared, handle, ensure_ascii=False, indent=2)

        self.logger.info("Prepared %s items for labeling -> %s", len(prepared), output_json)
        return output_json

    def clean_text(self, text: str) -> str:
        text = text.translate(TRANSLATION_TABLE)
        text = unicodedata.normalize("NFKC", text)
        if self.config.enable_emoji_removal:
            text = EMOJI_REGEX.sub("", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _passes_length_checks(self, text: str) -> bool:
        if len(text) < self.config.min_length:
            return False
        chinese_chars = sum(1 for ch in text if self._is_cjk(ch))
        if chinese_chars < self.config.min_chinese_chars:
            return False
        return True

    @staticmethod
    def _is_cjk(char: str) -> bool:
        codepoint = ord(char)
        return (
            0x4E00 <= codepoint <= 0x9FFF
            or 0x3400 <= codepoint <= 0x4DBF
            or 0x20000 <= codepoint <= 0x2A6DF
            or 0x2A700 <= codepoint <= 0x2B73F
            or 0x2B740 <= codepoint <= 0x2B81F
            or 0x2B820 <= codepoint <= 0x2CEAF
        )
