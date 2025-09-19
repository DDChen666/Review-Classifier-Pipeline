
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
import requests

from ..config import AppStoreCrawlerConfig
from .base import BaseCrawler


@dataclass
class AppStoreCrawler(BaseCrawler):
    config: AppStoreCrawlerConfig
    logger: logging.Logger = logging.getLogger("review_pipeline.crawlers.app_store")

    name: str = "app_store"

    def fetch(self) -> pd.DataFrame:
        if not self.config or not self.config.enabled:
            self.logger.info("App Store crawler disabled; skipping fetch.")
            return pd.DataFrame()

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        reviews_data = []
        page = 1
        max_pages = self.config.max_pages
        self.logger.info(
            "Fetching App Store reviews app_id=%s country=%s count=%s",
            self.config.app_id,
            self.config.country,
            self.config.review_count,
        )

        try:
            while len(reviews_data) < self.config.review_count:
                if max_pages is not None and page > max_pages:
                    self.logger.info("Reached configured max_pages=%s", max_pages)
                    break

                url = (
                    f"https://itunes.apple.com/{self.config.country}/rss/customerreviews/"
                    f"id={self.config.app_id}/sortBy=mostRecent/page={page}/json"
                )

                try:
                    response = session.get(url, timeout=15)
                    response.raise_for_status()
                    data = response.json()
                except (requests.RequestException, ValueError) as exc:
                    self.logger.error("App Store request failed on page %s: %s", page, exc)
                    break

                entries = data.get("feed", {}).get("entry", [])
                if len(entries) <= 1:
                    self.logger.info("No more App Store reviews after page %s", page)
                    break

                for entry in entries[1:]:
                    review = self._parse_entry(entry)
                    if review:
                        reviews_data.append(review)
                        if len(reviews_data) >= self.config.review_count:
                            break

                self.logger.debug("Fetched %s entries from page %s", len(entries) - 1, page)
                page += 1
                time.sleep(self.config.request_delay)

        finally:
            session.close()

        df = pd.DataFrame(reviews_data)
        self.logger.info("Fetched %s App Store reviews", len(df))
        return df

    def _parse_entry(self, entry: Dict[str, object]) -> Optional[Dict[str, object]]:
        try:
            author_name = (
                entry.get("author", {}).get("name", {}).get("label", "Unknown")
            )
            content = entry.get("content", {}).get("label", "")
            rating = int(entry.get("im:rating", {}).get("label", "0"))
            title = entry.get("title", {}).get("label", "")
            review_id = entry.get("id", {}).get("label", "")
            updated = entry.get("updated", {}).get("label", "")
            review_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))

            return {
                "reviewId": review_id,
                "userName": author_name,
                "rating": rating,
                "date": review_date.strftime("%Y-%m-%d %H:%M:%S"),
                "title": title,
                "review": content,
                "isEdited": False,
            }
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.debug("Failed to parse App Store entry: %s", exc)
            return None
