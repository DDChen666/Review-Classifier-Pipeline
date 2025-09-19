
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from google_play_scraper import Sort, reviews

from ..config import GooglePlayCrawlerConfig
from .base import BaseCrawler


@dataclass
class GooglePlayCrawler(BaseCrawler):
    config: GooglePlayCrawlerConfig
    logger: logging.Logger = logging.getLogger("review_pipeline.crawlers.google_play")

    name: str = "google_play"

    def fetch(self) -> pd.DataFrame:
        if not self.config or not self.config.enabled:
            self.logger.info("Google Play crawler disabled; skipping fetch.")
            return pd.DataFrame()

        self.logger.info(
            "Fetching Google Play reviews app_id=%s country=%s lang=%s count=%s",
            self.config.app_id,
            self.config.country,
            self.config.lang,
            self.config.review_count,
        )

        try:
            raw_reviews, _ = reviews(
                self.config.app_id,
                lang=self.config.lang,
                country=self.config.country,
                sort=Sort.NEWEST,
                count=self.config.review_count,
            )
        except Exception as exc:  # pragma: no cover - network errors
            self.logger.error("Failed to fetch Google Play reviews: %s", exc)
            return pd.DataFrame()

        df = pd.DataFrame(raw_reviews)
        if df.empty:
            self.logger.warning("No Google Play reviews returned.")
            return df

        column_map = {
            "score": "rating",
            "at": "date",
            "content": "review",
        }
        for source, target in column_map.items():
            if source in df.columns:
                df[target] = df[source]

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

        self.logger.info("Fetched %s Google Play reviews", len(df))
        return df
