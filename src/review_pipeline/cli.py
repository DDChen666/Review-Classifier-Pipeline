
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click

from .config import ProjectConfig, load_config
from .logging_utils import setup_logging
from .pipeline.orchestrator import ReviewPipeline


def _initialise_pipeline(config_path: str) -> ReviewPipeline:
    config_file = Path(config_path).expanduser().resolve()
    config = load_config(config_file, project_root=config_file.parent.parent)
    setup_logging(config.logging)
    return ReviewPipeline(config)


@click.group()
@click.option(
    "--config",
    "config_path",
    default="config/config.yaml",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    show_default=True,
)
@click.pass_context
def cli(ctx: click.Context, config_path: str) -> None:
    """Command-line interface for the review pipeline."""

    pipeline = _initialise_pipeline(config_path)
    ctx.obj = {
        "config_path": config_path,
        "pipeline": pipeline,
    }


@cli.command()
@click.option("--timestamp", type=str, default=None, help="Override timestamp used for filenames.")
@click.pass_context
def crawl(ctx: click.Context, timestamp: Optional[str]) -> None:
    """Fetch reviews from configured sources."""

    pipeline: ReviewPipeline = ctx.obj["pipeline"]
    outputs = pipeline.run_crawl(timestamp)
    click.echo(json.dumps({k: str(v) if v else None for k, v in outputs.items()}, indent=2, ensure_ascii=False))


@cli.command()
@click.option("--google-csv", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--app-store-csv", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--timestamp", type=str, default=None)
@click.pass_context
def merge(
    ctx: click.Context,
    google_csv: Optional[str],
    app_store_csv: Optional[str],
    timestamp: Optional[str],
) -> None:
    """Merge platform CSV files into a unified dataset."""

    if not google_csv and not app_store_csv:
        raise click.UsageError("Provide at least one CSV input via --google-csv or --app-store-csv.")

    pipeline: ReviewPipeline = ctx.obj["pipeline"]
    output = pipeline.run_merge(
        Path(google_csv) if google_csv else None,
        Path(app_store_csv) if app_store_csv else None,
        timestamp,
    )
    click.echo(str(output))


@cli.command(name="prepare-labeling")
@click.option("--merged-csv", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--timestamp", type=str, default=None)
@click.pass_context
def prepare_labeling(ctx: click.Context, merged_csv: str, timestamp: Optional[str]) -> None:
    """Create a cleaned unlabeled dataset ready for annotation."""

    pipeline: ReviewPipeline = ctx.obj["pipeline"]
    output = pipeline.prepare_labeling(Path(merged_csv), timestamp)
    click.echo(str(output))


@cli.command()
@click.option("--unlabeled-json", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--timestamp", type=str, default=None)
@click.option("--skip-validation", is_flag=True, default=False, help="Skip automatic validation loop.")
@click.pass_context
def label(
    ctx: click.Context,
    unlabeled_json: str,
    timestamp: Optional[str],
    skip_validation: bool,
) -> None:
    """Run the configured labeler and optional validation/fixing."""

    pipeline: ReviewPipeline = ctx.obj["pipeline"]
    results = pipeline.run_labeling(Path(unlabeled_json), timestamp, run_validation=not skip_validation)
    click.echo(json.dumps({k: str(v) if v else None for k, v in results.items()}, indent=2, ensure_ascii=False))


@cli.command()
@click.option("--labeled-json", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--timestamp", type=str, default=None)
@click.pass_context
def split(ctx: click.Context, labeled_json: str, timestamp: Optional[str]) -> None:
    """Split labeled dataset into train/test partitions."""

    pipeline: ReviewPipeline = ctx.obj["pipeline"]
    results = pipeline.run_split(Path(labeled_json), timestamp)
    click.echo(json.dumps({k: str(v) for k, v in results.items()}, indent=2, ensure_ascii=False))


@cli.command(name="run-all")
@click.pass_context
def run_all(ctx: click.Context) -> None:
    """Execute the full end-to-end pipeline."""

    pipeline: ReviewPipeline = ctx.obj["pipeline"]
    results = pipeline.run_all()
    click.echo(json.dumps({k: str(v) for k, v in results.items()}, indent=2, ensure_ascii=False))
