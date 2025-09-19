from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, validator


class PathsConfig(BaseModel):
    """Filesystem locations used throughout the pipeline."""

    base_output_dir: Path = Field(default=Path("data"))
    raw_dir: Path = Field(default=Path("data/raw"))
    processed_dir: Path = Field(default=Path("data/processed"))
    labeling_dir: Path = Field(default=Path("data/labeling"))
    splits_dir: Path = Field(default=Path("data/splits"))
    logs_dir: Path = Field(default=Path("logs"))

    def resolve(self, project_root: Path) -> "PathsConfig":
        """Return a copy with paths resolved relative to *project_root*."""

        resolved = {}
        for field_name, value in self.dict().items():
            path = Path(value)
            if not path.is_absolute():
                path = (project_root / path).resolve()
            path.mkdir(parents=True, exist_ok=True)
            resolved[field_name] = path
        return PathsConfig(**resolved)


class GooglePlayCrawlerConfig(BaseModel):
    enabled: bool = Field(default=True)
    app_id: str
    lang: str = Field(default="zh_TW")
    country: str = Field(default="tw")
    review_count: int = Field(default=200, ge=1)


class AppStoreCrawlerConfig(BaseModel):
    enabled: bool = Field(default=True)
    app_id: int
    country: str = Field(default="tw")
    review_count: int = Field(default=200, ge=1)
    request_delay: float = Field(default=1.0, ge=0.0)
    max_pages: Optional[int] = Field(default=None, ge=1)


class ScrapingConfig(BaseModel):
    google_play: Optional[GooglePlayCrawlerConfig] = None
    app_store: Optional[AppStoreCrawlerConfig] = None


class MergingConfig(BaseModel):
    output_filename_pattern: str = Field(default="merged_reviews_{timestamp}.csv")
    encoding: str = Field(default="utf-8-sig")


class CleaningConfig(BaseModel):
    min_length: int = Field(default=1, ge=0)
    min_chinese_chars: int = Field(default=2, ge=0)
    enable_emoji_removal: bool = Field(default=True)


class GeminiConfig(BaseModel):
    api_key_env: str = Field(default="GEMINI_API_KEY")
    model: str = Field(default="gemini-2.5-flash")
    batch_size: int = Field(default=100, ge=1)
    max_retries: int = Field(default=5, ge=0)
    retry_delay_sec: float = Field(default=30.0, ge=0.0)
    validate_max_rounds: int = Field(default=8, ge=1)


class LabelingConfig(BaseModel):
    provider: str = Field(default="gemini")
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)

    @validator("provider")
    def validate_provider(cls, value: str) -> str:
        allowed = {"gemini"}
        if value not in allowed:
            raise ValueError(f"Unsupported labeler provider: {value}. Allowed: {allowed}")
        return value


class SplittingConfig(BaseModel):
    test_size: float = Field(default=0.2, gt=0.0, lt=1.0)
    random_state: int = Field(default=42)
    stratify_field: str = Field(default="primary")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    fmt: str = Field(default="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    file: str = Field(default="logs/pipeline.log")


class ProjectConfig(BaseModel):
    paths: PathsConfig = Field(default_factory=PathsConfig)
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    merging: MergingConfig = Field(default_factory=MergingConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    labeling: LabelingConfig = Field(default_factory=LabelingConfig)
    splitting: SplittingConfig = Field(default_factory=SplittingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def resolved(self, project_root: Path) -> "ProjectConfig":
        resolved_paths = self.paths.resolve(project_root)

        logging_file = Path(self.logging.file)
        if not logging_file.is_absolute():
            logging_file = (project_root / logging_file).resolve()
        logging_file.parent.mkdir(parents=True, exist_ok=True)

        logging_config = self.logging.copy(update={"file": str(logging_file)})

        return ProjectConfig(
            paths=resolved_paths,
            scraping=self.scraping,
            merging=self.merging,
            cleaning=self.cleaning,
            labeling=self.labeling,
            splitting=self.splitting,
            logging=logging_config,
        )


def load_config(config_path: Path, project_root: Optional[Path] = None) -> ProjectConfig:
    """Load the YAML *config_path* into a :class:`ProjectConfig`."""

    config_path = config_path.resolve()
    if project_root is None:
        project_root = config_path.parent.parent if config_path.is_absolute() else Path.cwd()

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data: Dict[str, Any] = yaml.safe_load(handle) or {}

    config = ProjectConfig(**data)
    return config.resolved(project_root)
