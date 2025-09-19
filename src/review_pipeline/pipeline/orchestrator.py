
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from ..config import ProjectConfig
from ..crawlers.app_store import AppStoreCrawler
from ..crawlers.google_play import GooglePlayCrawler
from ..processors.cleaning import LabelingDatasetPreparer
from ..processors.labeling import LabelingWorkflow
from ..processors.merger import ReviewMerger
from ..processors.splitter import DatasetSplitter
from ..utils.files import ensure_parent_dir, timestamped_filename


@dataclass
class ReviewPipeline:
    config: ProjectConfig
    logger: logging.Logger = logging.getLogger("review_pipeline.pipeline.orchestrator")

    def run_crawl(self, timestamp: Optional[str] = None) -> Dict[str, Optional[Path]]:
        outputs: Dict[str, Optional[Path]] = {"google_play": None, "app_store": None}

        google_cfg = self.config.scraping.google_play
        if google_cfg:
            crawler = GooglePlayCrawler(google_cfg)
            df = crawler.fetch()
            if not df.empty:
                filename = timestamped_filename("google_play_reviews_{timestamp}.csv", timestamp)
                path = ensure_parent_dir(self.config.paths.raw_dir / filename)
                df.to_csv(path, index=False, encoding="utf-8-sig")
                outputs["google_play"] = path
                self.logger.info("Google Play reviews saved to %s", path)
            else:
                self.logger.warning("Google Play crawler returned no data.")

        app_store_cfg = self.config.scraping.app_store
        if app_store_cfg:
            crawler = AppStoreCrawler(app_store_cfg)
            df = crawler.fetch()
            if not df.empty:
                filename = timestamped_filename("app_store_reviews_{timestamp}.csv", timestamp)
                path = ensure_parent_dir(self.config.paths.raw_dir / filename)
                df.to_csv(path, index=False, encoding="utf-8-sig")
                outputs["app_store"] = path
                self.logger.info("App Store reviews saved to %s", path)
            else:
                self.logger.warning("App Store crawler returned no data.")

        return outputs

    def run_merge(
        self,
        google_csv: Optional[Path],
        app_store_csv: Optional[Path],
        timestamp: Optional[str] = None,
    ) -> Path:
        merger = ReviewMerger(self.config.merging)
        filename = timestamped_filename(self.config.merging.output_filename_pattern, timestamp)
        output = ensure_parent_dir(self.config.paths.processed_dir / filename)
        return merger.merge_from_files(google_csv, app_store_csv, output)

    def prepare_labeling(self, merged_csv: Path, timestamp: Optional[str] = None) -> Path:
        preparer = LabelingDatasetPreparer(self.config.cleaning)
        filename = timestamped_filename("unlabeled_reviews_{timestamp}.json", timestamp)
        output = ensure_parent_dir(self.config.paths.labeling_dir / filename)
        return preparer.prepare(merged_csv, output)

    def run_labeling(
        self,
        unlabeled_json: Path,
        timestamp: Optional[str] = None,
        run_validation: bool = True,
    ) -> Dict[str, Optional[Path]]:
        workflow = LabelingWorkflow(self.config.labeling)
        labeled_filename = timestamped_filename("labeled_reviews_{timestamp}.json", timestamp)
        labeled_output = ensure_parent_dir(self.config.paths.labeling_dir / labeled_filename)
        fixed_output: Optional[Path] = None
        if run_validation:
            fixed_filename = labeled_filename.replace(".json", "_fixed.json")
            fixed_output = ensure_parent_dir(self.config.paths.labeling_dir / fixed_filename)
        return workflow.run(unlabeled_json, labeled_output, fixed_output, run_validation=run_validation)

    def run_split(
        self,
        labeled_json: Path,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Path]:
        splitter = DatasetSplitter(self.config.splitting)
        train_file = timestamped_filename("train_set_{timestamp}.json", timestamp)
        test_file = timestamped_filename("test_set_{timestamp}.json", timestamp)
        train_path = ensure_parent_dir(self.config.paths.splits_dir / train_file)
        test_path = ensure_parent_dir(self.config.paths.splits_dir / test_file)
        return splitter.split(labeled_json, train_path, test_path)

    def run_all(self) -> Dict[str, Path]:
        timestamp = timestamped_filename("{timestamp}")
        crawl_outputs = self.run_crawl(timestamp)
        merged_path = self.run_merge(
            crawl_outputs.get("google_play"),
            crawl_outputs.get("app_store"),
            timestamp,
        )
        unlabeled_path = self.prepare_labeling(merged_path, timestamp)
        labeling_outputs = self.run_labeling(unlabeled_path, timestamp)
        labeled_path = labeling_outputs.get("fixed_path") or labeling_outputs["labeled_path"]
        split_outputs = self.run_split(labeled_path, timestamp)

        results: Dict[str, Path] = {
            "google_play_csv": crawl_outputs.get("google_play"),
            "app_store_csv": crawl_outputs.get("app_store"),
            "merged_csv": merged_path,
            "unlabeled_json": unlabeled_path,
            "labeled_json": labeling_outputs["labeled_path"],
            "fixed_json": labeling_outputs.get("fixed_path", labeling_outputs["labeled_path"]),
            "train_json": split_outputs["train_path"],
            "test_json": split_outputs["test_path"],
        }
        return {key: value for key, value in results.items() if value is not None}
