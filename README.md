# Review Classifier Pipeline

A configurable, extensible pipeline for scraping app-store reviews, unifying and cleaning the data, running automated labeling with large language models, and producing stratified dataset splits ready for downstream ML workflows.

## Highlights

- **Configuration-driven**: all runtime options live in `config/config.yaml`; no hard-coded parameters in the Python sources.
- **Composable CLI**: `main.py` exposes modular commands (`crawl`, `merge`, `prepare-labeling`, `label`, `split`, `run-all`). Each stage accepts explicit input/output paths so you always know which artefact is consumed next—no fragile "latest file" heuristics.
- **Extensible abstractions**: crawlers, processors, and labelers share simple base interfaces, making it straightforward to plug in new data sources or AI models.
- **Robust labeling loop**: the Gemini labeler batches requests, validates outputs against strict schemas, and automatically re-labels any invalid samples.
- **Production-ready ergonomics**: central logging, dependency declaration, deterministic filenames with timestamps, and a clearly defined repository layout.

## Repository Layout

```
.
├── config/
│   └── config.yaml             # Project-wide settings
├── data/                       # Runtime artefacts (ignored, `.gitkeep` placeholder)
├── legacy_scripts/             # Original prototype scripts preserved for reference
├── logs/                       # Log files (ignored, `.gitkeep` placeholder)
├── src/
│   └── review_pipeline/
│       ├── __init__.py
│       ├── cli.py              # Click CLI wiring
│       ├── config.py           # Pydantic config models + loader
│       ├── logging_utils.py    # Logging bootstrapper
│       ├── crawlers/
│       │   ├── base.py         # Abstract crawler contract
│       │   ├── app_store.py
│       │   └── google_play.py
│       ├── processors/
│       │   ├── cleaning.py     # Text normalisation + unlabeled JSON writer
│       │   ├── labeling.py     # Labeling workflow orchestration
│       │   ├── merger.py       # Platform-specific dataframe merge
│       │   └── splitter.py     # Stratified train/test split
│       ├── labelers/
│       │   ├── base.py         # BaseLabeler ABC
│       │   └── gemini.py       # Gemini-powered labeler + validation logic
│       ├── pipeline/
│       │   └── orchestrator.py # High-level pipeline facade
│       └── utils/
│           └── files.py
├── main.py                     # Entry point wiring `src/` onto sys.path and invoking CLI
├── requirements.txt            # Python dependencies
└── .gitignore
```

## Getting Started

1. **Install dependencies**
   ```bash
   python -m venv .venv
   .venv\Scriptsctivate          # PowerShell on Windows
   pip install -r requirements.txt
   ```

2. **Provide secrets**
   - Create a `.env` file (already ignored) and set `GEMINI_API_KEY=<your-api-key>`.
   - Alternatively, export the environment variable before running any commands.

3. **Tune configuration**
   - Edit `config/config.yaml` to change app IDs, review counts, cleaning thresholds, or model settings.
   - Every section is documented below.

4. **Run individual stages**
   ```bash
   python main.py crawl --timestamp 20250919_120000
   python main.py merge --google-csv data/raw/google_play_reviews_20250919_120000.csv --app-store-csv data/raw/app_store_reviews_20250919_120000.csv
   python main.py prepare-labeling --merged-csv data/processed/merged_reviews_20250919_120000.csv
   python main.py label --unlabeled-json data/labeling/unlabeled_reviews_20250919_120000.json
   python main.py split --labeled-json data/labeling/labeled_reviews_20250919_120000_fixed.json
   ```

5. **Or run end-to-end**
   ```bash
   python main.py run-all
   ```
   The command returns a JSON summary containing every generated artefact path. Filenames are timestamped, and each downstream stage explicitly receives the upstream artefact path from the orchestrator.

## Configuration Reference (`config/config.yaml`)

### `paths`
Controls where generated artefacts and logs reside. Paths may be relative to project root or absolute. All directories are created on demand.

### `scraping`
Two optional crawler blocks (`google_play`, `app_store`). Toggle each via `enabled`. Provide app IDs, locale/country, and desired review counts. App Store crawling also supports `request_delay` (seconds) and an optional `max_pages` safeguard.

### `merging`
Defines the merged CSV filename pattern (must include `{timestamp}`) and the encoding used when reading/writing reviews.

### `cleaning`
Text normalisation before labeling: minimum character requirements, emoji stripping toggle, and other heuristics. Produces an unlabeled JSON array ready for annotation.

### `labeling`
- `provider`: currently `gemini` (hook for future providers).
- `gemini`: environment variable name, model ID, batching, retry/timeout policy, and validation loop settings.

The Gemini implementation loads `.env`, calls the Google GenAI client, validates outputs, and re-labels invalid samples until all pass or the configured round limit is reached.

### `splitting`
Controls the stratified train/test split: `test_size`, `random_state`, and the column used for stratification (default `primary`).

### `logging`
Standard logging level, format string, and log file location. A rotating file handler (5 MB × 3 backups) is configured in addition to console output.

## CLI Commands

| Command | Purpose | Key options |
|---------|---------|-------------|
| `crawl` | Run enabled crawlers and store raw CSVs | `--timestamp` overrides the timestamp used in filenames |
| `merge` | Combine one or both platform CSVs into the unified schema | `--google-csv`, `--app-store-csv`, `--timestamp` |
| `prepare-labeling` | Clean merged CSV and emit unlabeled JSON | `--merged-csv`, `--timestamp` |
| `label` | Annotate unlabeled JSON and optionally run validation/fixing | `--unlabeled-json`, `--timestamp`, `--skip-validation` |
| `split` | Produce stratified train/test JSON sets | `--labeled-json`, `--timestamp` |
| `run-all` | Execute the full pipeline using one shared timestamp | (inherits CLI config option only) |

All commands respect the `--config` option to point at a different YAML file.

## Extensibility Notes

- **Adding a crawler**: implement `BaseCrawler.fetch()` in a new class under `src/review_pipeline/crawlers/`, register its configuration block in `config/config.yaml`, and wire it inside `ReviewPipeline.run_crawl`.
- **Adding a labeler**: subclass `BaseLabeler`, provide `annotate` + `validate`, expose configuration via `LabelingConfig`, and update `LabelingWorkflow.__post_init__` with the new provider key.
- **Custom processors**: follow the structure in `processors/`—encapsulate the logic behind a simple method and orchestrate it through `pipeline/orchestrator.py` so the CLI automatically benefits.

## Logs & Artefacts

- Logs land in `logs/pipeline.log` (rotating). Adjust format/level in the config file or tail the console output for quick feedback.
- Generated datasets live under `data/`, split into `raw/`, `processed/`, `labeling/`, and `splits/`. The `.gitkeep` placeholders keep the folders in Git while ignoring actual artefacts.

## Legacy Scripts

The original monolithic notebooks/scripts were moved to `legacy_scripts/` for reference. They are no longer executed by the new pipeline but can serve as historical context while transitioning.

## Verification

- `python -m compileall src main.py` — ensures all modules parse correctly.
- Functional runs require the dependencies installed and valid API credentials; see the quick start instructions above.

## Next Steps

- Configure additional crawler sources or alternative labeling providers as needed.
- Integrate automated tests (e.g., fixtures with stubbed responses) to guard critical processors.
- Containerise the CLI or wire into an orchestration service/cron once the pipeline stabilises.
