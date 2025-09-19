
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from ..config import MergingConfig


@dataclass
class ReviewMerger:
    config: MergingConfig
    logger: logging.Logger = logging.getLogger("review_pipeline.processors.merger")

    unified_columns = ["platform", "reviewId", "userName", "rating", "date", "content"]

    def merge_frames(
        self,
        google_df: Optional[pd.DataFrame] = None,
        app_store_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        frames = []
        if google_df is not None and not google_df.empty:
            frames.append(self._normalise_google_play(google_df))
        if app_store_df is not None and not app_store_df.empty:
            frames.append(self._normalise_app_store(app_store_df))

        if not frames:
            self.logger.warning("No review data supplied for merging.")
            return pd.DataFrame(columns=self.unified_columns)

        merged = pd.concat(frames, ignore_index=True)
        merged.drop_duplicates(subset=["reviewId"], keep="first", inplace=True)
        merged = merged[self.unified_columns]
        self.logger.info("Merged %s reviews", len(merged))
        return merged

    def merge_from_files(
        self,
        google_csv: Optional[Path],
        app_store_csv: Optional[Path],
        output_path: Path,
    ) -> Path:
        google_df = self._load_csv(google_csv) if google_csv else None
        app_store_df = self._load_csv(app_store_csv) if app_store_csv else None
        merged = self.merge_frames(google_df, app_store_df)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(output_path, index=False, encoding=self.config.encoding)
        self.logger.info("Merged reviews saved to %s", output_path)
        return output_path

    def _load_csv(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path, encoding=self.config.encoding)
        self.logger.info("Loaded %s rows from %s", len(df), path)
        return df

    def _normalise_google_play(self, df: pd.DataFrame) -> pd.DataFrame:
        renamed = df.rename(
            columns={"review": "content", "date": "date", "rating": "rating"}
        ).copy()
        renamed["platform"] = "google_play"
        renamed["content"] = renamed["content"].fillna("")
        renamed["date"] = renamed["date"].fillna("")
        return renamed[self.unified_columns]

    def _normalise_app_store(self, df: pd.DataFrame) -> pd.DataFrame:
        renamed = df.rename(columns={"review": "content"}).copy()
        renamed["platform"] = "app_store"
        renamed["content"] = renamed["content"].fillna("")
        renamed["date"] = renamed["date"].fillna("")
        return renamed[self.unified_columns]
