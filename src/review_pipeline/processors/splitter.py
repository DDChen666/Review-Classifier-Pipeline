
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import pandas as pd
from sklearn.model_selection import train_test_split

from ..config import SplittingConfig


@dataclass
class DatasetSplitter:
    config: SplittingConfig
    logger: logging.Logger = logging.getLogger("review_pipeline.processors.splitter")

    def split(self, labeled_json: Path, train_output: Path, test_output: Path) -> Dict[str, Path]:
        with labeled_json.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        df = pd.DataFrame(data)
        self.logger.info("Loaded %s labeled rows from %s", len(df), labeled_json)

        if df.empty:
            raise ValueError("Labeled dataset is empty; cannot split.")

        stratify_field = self.config.stratify_field
        if stratify_field not in df.columns:
            raise ValueError(f"Stratify field '{stratify_field}' not present in dataset.")
        if df[stratify_field].isnull().any():
            raise ValueError(f"Stratify field '{stratify_field}' contains null values.")
        if (df[stratify_field].value_counts() < 2).any():
            self.logger.warning(
                "Some classes have fewer than two samples; stratified split may fail."
            )

        train_df, test_df = train_test_split(
            df,
            test_size=self.config.test_size,
            random_state=self.config.random_state,
            stratify=df[stratify_field],
        )

        train_output.parent.mkdir(parents=True, exist_ok=True)
        test_output.parent.mkdir(parents=True, exist_ok=True)

        train_df.to_json(train_output, orient="records", force_ascii=False, indent=2)
        test_df.to_json(test_output, orient="records", force_ascii=False, indent=2)

        self.logger.info(
            "Dataset split complete: %s train rows -> %s, %s test rows -> %s",
            len(train_df),
            train_output,
            len(test_df),
            test_output,
        )

        return {"train_path": train_output, "test_path": test_output}
