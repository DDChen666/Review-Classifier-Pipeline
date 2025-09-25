# Review Classifier Pipeline

**Language / 語言：** [繁體中文](#繁體中文) | [简体中文](#简体中文) | [English](#english)

## 繁體中文

一個可配置、可擴展的管線，用於抓取應用商店評論，統一與清洗資料，藉助大型語言模型完成自動標註，併產生適合下游機器學習流程的分層數據集。

### 項目亮點

- **配置驅動**：所有運行參數均存放於 `config/config.yaml`，Python 源碼中沒有硬編碼常量。
- **可組合 CLI**：`main.py` 提供模塊化指令（`crawl`、`merge`、`prepare-labeling`、`label`、`split`、`run-all`）。每個階段都顯式接收輸入輸出路徑，避免依賴「最新文件」這類脆弱的推測。
- **可擴展抽象**：爬蟲、處理器與標註器共享簡單的基類接口，便於插入新的數據來源或 AI 模型。
- **健壯的標註循環**：Gemini 標註器支持批次請求、嚴格的輸出驗證，並會自動重新標註任何無效樣本。
- **面向生產的體驗**：集中化日誌、依賴聲明、帶時間戳的確定性文件名、清晰的倉庫結構。

### 倉庫結構

```
.
├── config/
│   └── config.yaml             # 全局設置
├── data/                       # 運行時產物（忽略，使用 `.gitkeep` 佔位）
├── legacy_scripts/             # 保留的原型腳本
├── logs/                       # 日誌文件（忽略，使用 `.gitkeep` 佔位）
├── src/
│   └── review_pipeline/
│       ├── __init__.py
│       ├── cli.py              # Click CLI 綁定
│       ├── config.py           # Pydantic 配置模型與加載器
│       ├── logging_utils.py    # 日誌初始化
│       ├── crawlers/
│       │   ├── base.py         # 抽象爬蟲約定
│       │   ├── app_store.py
│       │   └── google_play.py
│       ├── processors/
│       │   ├── cleaning.py     # 文本規範化 + 未標註 JSON 輸出
│       │   ├── labeling.py     # 標註工作流編排
│       │   ├── merger.py       # 平臺合併邏輯
│       │   └── splitter.py     # 分層訓練/測試劃分
│       ├── labelers/
│       │   ├── base.py         # BaseLabeler 抽象類
│       │   └── gemini.py       # Gemini 標註器與驗證邏輯
│       ├── pipeline/
│       │   └── orchestrator.py # 高階管線封裝
│       └── utils/
│           └── files.py
├── main.py                     # 入口腳本，注入 `src/` 並調用 CLI
├── requirements.txt            # Python 依賴
└── .gitignore
```

### 快速開始

1. **安裝依賴**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate         # Windows PowerShell
   pip install -r requirements.txt
   ```

2. **配置密鑰**
   - 創建（或更新）`.env` 文件，並設置 `GEMINI_API_KEY=<your-api-key>`。
   - 或者在運行命令前導出相應的環境變量。

3. **調整配置**
   - 編輯 `config/config.yaml` 以更改應用 ID、評論數量、清洗閾值或模型設置。
   - 每個配置段落在下方均有說明。

4. **運行單獨階段**
   ```bash
   python main.py crawl --timestamp 20250919_120000
   python main.py merge --google-csv data/raw/google_play_reviews_20250919_120000.csv --app-store-csv data/raw/app_store_reviews_20250919_120000.csv
   python main.py prepare-labeling --merged-csv data/processed/merged_reviews_20250919_120000.csv
   python main.py label --unlabeled-json data/labeling/unlabeled_reviews_20250919_120000.json
   python main.py split --labeled-json data/labeling/labeled_reviews_20250919_120000_fixed.json
   ```

5. **一鍵執行全流程**
   ```bash
   python main.py run-all
   ```
   該命令會返回包含所有生成產物路徑的 JSON 摘要。文件名帶有時間戳，每個階段都由調度器顯式傳遞上游產物路徑。

### 配置參考（`config/config.yaml`）

#### `paths`
控制生成產物與日誌的存放位置，可使用項目根目錄的相對路徑或絕對路徑。目錄會在需要時自動創建。

#### `scraping`
可選的兩組爬蟲配置（`google_play`、`app_store`）。可通過 `enabled` 開關。需要提供應用 ID、地區/國家以及目標評論數量。App Store 爬蟲還支持 `request_delay`（秒）與可選的 `max_pages` 限制。

#### `merging`
定義合併後 CSV 的文件名模式（必須包含 `{timestamp}`）以及讀寫評論時的編碼。

#### `cleaning`
標註前的文本規範化：最小字符數、是否移除表情符號等。輸出可供標註的未標註 JSON 數組。

#### `labeling`
- `provider`：當前支持 `gemini`（爲未來擴展預留）。
- `gemini`：包括環境變量名、模型 ID、批次與重試/超時策略、驗證循環設置。

Gemini 實現會加載 `.env`，調用 Google GenAI 客戶端，驗證輸出，並在所有樣本通過或達到輪次上限前重複標註。

#### `splitting`
控制分層訓練/測試劃分：`test_size`、`random_state` 以及用於分層的列（默認 `primary`）。

#### `logging`
標準日誌等級、格式以及文件位置。除了控制檯輸出，還配置了 5 MB × 3 份備份的輪轉日誌。

### CLI 指令

| 指令 | 功能 | 關鍵選項 |
|------|------|----------|
| `crawl` | 運行已啓用的爬蟲並保存原始 CSV | `--timestamp` 可覆蓋文件名使用的時間戳 |
| `merge` | 合併一個或兩個平臺 CSV 爲統一格式 | `--google-csv`、`--app-store-csv`、`--timestamp` |
| `prepare-labeling` | 清洗合併後的 CSV 並輸出未標註 JSON | `--merged-csv`、`--timestamp` |
| `label` | 標註未標註 JSON，可選跳過驗證/修復 | `--unlabeled-json`、`--timestamp`、`--skip-validation` |
| `split` | 生成分層的訓練/測試 JSON | `--labeled-json`、`--timestamp` |
| `run-all` | 以單一時間戳執行完整管線 | （僅繼承 CLI 的配置選項） |

所有指令都支持 `--config` 參數以指定不同的 YAML 配置。

### 可擴展性

- **新增爬蟲**：在 `src/review_pipeline/crawlers/` 下實現繼承 `BaseCrawler` 的類，註冊對應配置，並在 `ReviewPipeline.run_crawl` 中接入。
- **新增標註器**：繼承 `BaseLabeler`，實現 `annotate` 與 `validate`，在 `LabelingConfig` 中暴露配置，並在 `LabelingWorkflow.__post_init__` 中註冊新的 provider。
- **自定義處理器**：參考 `processors/` 結構，將邏輯封裝在簡單方法中，並通過 `pipeline/orchestrator.py` 編排，即可自動獲得 CLI 支持。

### 日誌與產物

- 日誌默認寫入 `logs/pipeline.log`（輪轉）。可在配置文件中調整格式/等級，或直接查看控制檯輸出。
- 數據集產物位於 `data/` 下的 `raw/`、`processed/`、`labeling/` 與 `splits/` 子目錄。倉庫中通過 `.gitkeep` 保留目錄結構。

### 舊版腳本

最初的單體筆記本/腳本保存在 `legacy_scripts/`，僅供參考，新管線不會調用，但可在遷移階段提供歷史背景。

### 驗證

- `python -m compileall src main.py` —— 確保所有模塊能正確解析。
- 運行功能需先安裝依賴並提供有效的 API 憑證，詳見快速開始章節。

### 後續計劃

- 根據需要配置更多爬蟲來源或替代的標註服務。
- 引入自動化測試（例如基於樁的響應）以保護關鍵處理器。
- 當管線穩定後，可容器化 CLI 或接入編排服務/計劃任務。

## 简体中文

一个可配置、可扩展的管线，用于抓取应用商店评论，统一与清洗资料，借助大型语言模型完成自动标注，并产生适合下游机器学习流程的分层数据集。

### 项目亮点

- **配置驱动**：所有运行参数均存放于 `config/config.yaml`，Python 源码中没有硬编码常量。
- **可组合 CLI**：`main.py` 提供模块化指令（`crawl`、`merge`、`prepare-labeling`、`label`、`split`、`run-all`）。每个阶段都显式接收输入输出路径，避免依赖「最新文件」这类脆弱的推测。
- **可扩展抽象**：爬虫、处理器与标注器共享简单的基类接口，便于插入新的数据来源或 AI 模型。
- **健壮的标注循环**：Gemini 标注器支持批次请求、严格的输出验证，并会自动重新标注任何无效样本。
- **面向生产的体验**：集中化日志、依赖声明、带时间戳的确定性文件名、清晰的仓库结构。

### 仓库结构

```
.
├── config/
│   └── config.yaml             # 全局设置
├── data/                       # 运行时产物（忽略，使用 `.gitkeep` 占位）
├── legacy_scripts/             # 保留的原型脚本
├── logs/                       # 日志文件（忽略，使用 `.gitkeep` 占位）
├── src/
│   └── review_pipeline/
│       ├── __init__.py
│       ├── cli.py              # Click CLI 绑定
│       ├── config.py           # Pydantic 配置模型与加载器
│       ├── logging_utils.py    # 日志初始化
│       ├── crawlers/
│       │   ├── base.py         # 抽象爬虫约定
│       │   ├── app_store.py
│       │   └── google_play.py
│       ├── processors/
│       │   ├── cleaning.py     # 文本规范化 + 未标注 JSON 输出
│       │   ├── labeling.py     # 标注工作流编排
│       │   ├── merger.py       # 平台合并逻辑
│       │   └── splitter.py     # 分层训练/测试划分
│       ├── labelers/
│       │   ├── base.py         # BaseLabeler 抽象类
│       │   └── gemini.py       # Gemini 标注器与验证逻辑
│       ├── pipeline/
│       │   └── orchestrator.py # 高阶管线封装
│       └── utils/
│           └── files.py
├── main.py                     # 入口脚本，注入 `src/` 并调用 CLI
├── requirements.txt            # Python 依赖
└── .gitignore
```

### 快速开始

1. **安装依赖**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate         # Windows PowerShell
   pip install -r requirements.txt
   ```

2. **配置密钥**
   - 创建（或更新）`.env` 文件，并设置 `GEMINI_API_KEY=<your-api-key>`。
   - 或者在运行命令前导出相应的环境变量。

3. **调整配置**
   - 编辑 `config/config.yaml` 以更改应用 ID、评论数量、清洗阈值或模型设置。
   - 每个配置段落在下方均有说明。

4. **运行单独阶段**
   ```bash
   python main.py crawl --timestamp 20250919_120000
   python main.py merge --google-csv data/raw/google_play_reviews_20250919_120000.csv --app-store-csv data/raw/app_store_reviews_20250919_120000.csv
   python main.py prepare-labeling --merged-csv data/processed/merged_reviews_20250919_120000.csv
   python main.py label --unlabeled-json data/labeling/unlabeled_reviews_20250919_120000.json
   python main.py split --labeled-json data/labeling/labeled_reviews_20250919_120000_fixed.json
   ```

5. **一键执行全流程**
   ```bash
   python main.py run-all
   ```
   该命令会返回包含所有生成产物路径的 JSON 摘要。文件名带有时间戳，每个阶段都由调度器显式传递上游产物路径。

### 配置参考（`config/config.yaml`）

#### `paths`
控制生成产物与日志的存放位置，可使用项目根目录的相对路径或绝对路径。目录会在需要时自动创建。

#### `scraping`
可选的两组爬虫配置（`google_play`、`app_store`）。可通过 `enabled` 开关。需要提供应用 ID、地区/国家以及目标评论数量。App Store 爬虫还支持 `request_delay`（秒）与可选的 `max_pages` 限制。

#### `merging`
定义合并后 CSV 的文件名模式（必须包含 `{timestamp}`）以及读写评论时的编码。

#### `cleaning`
标注前的文本规范化：最小字符数、是否移除表情符号等。输出可供标注的未标注 JSON 数组。

#### `labeling`
- `provider`：当前支持 `gemini`（为未来扩展预留）。
- `gemini`：包括环境变量名、模型 ID、批次与重试/超时策略、验证循环设置。

Gemini 实现会加载 `.env`，调用 Google GenAI 客户端，验证输出，并在所有样本通过或达到轮次上限前重复标注。

#### `splitting`
控制分层训练/测试划分：`test_size`、`random_state` 以及用于分层的列（默认 `primary`）。

#### `logging`
标准日志等级、格式以及文件位置。除了控制台输出，还配置了 5 MB × 3 份备份的轮转日志。

### CLI 指令

| 指令 | 功能 | 关键选项 |
|------|------|----------|
| `crawl` | 运行已启用的爬虫并保存原始 CSV | `--timestamp` 可覆盖文件名使用的时间戳 |
| `merge` | 合并一个或两个平台 CSV 为统一格式 | `--google-csv`、`--app-store-csv`、`--timestamp` |
| `prepare-labeling` | 清洗合并后的 CSV 并输出未标注 JSON | `--merged-csv`、`--timestamp` |
| `label` | 标注未标注 JSON，可选跳过验证/修复 | `--unlabeled-json`、`--timestamp`、`--skip-validation` |
| `split` | 生成分层的训练/测试 JSON | `--labeled-json`、`--timestamp` |
| `run-all` | 以单一时间戳执行完整管线 | （仅继承 CLI 的配置选项） |

所有指令都支持 `--config` 参数以指定不同的 YAML 配置。

### 可扩展性

- **新增爬虫**：在 `src/review_pipeline/crawlers/` 下实现继承 `BaseCrawler` 的类，注册对应配置，并在 `ReviewPipeline.run_crawl` 中接入。
- **新增标注器**：继承 `BaseLabeler`，实现 `annotate` 与 `validate`，在 `LabelingConfig` 中暴露配置，并在 `LabelingWorkflow.__post_init__` 中注册新的 provider。
- **自定义处理器**：参考 `processors/` 结构，将逻辑封装在简单方法中，并通过 `pipeline/orchestrator.py` 编排，即可自动获得 CLI 支持。

### 日志与产物

- 日志默认写入 `logs/pipeline.log`（轮转）。可在配置文件中调整格式/等级，或直接查看控制台输出。
- 数据集产物位于 `data/` 下的 `raw/`、`processed/`、`labeling/` 与 `splits/` 子目录。仓库中通过 `.gitkeep` 保留目录结构。

### 旧版脚本

最初的单体笔记本/脚本保存在 `legacy_scripts/`，仅供参考，新管线不会调用，但可在迁移阶段提供历史背景。

### 验证

- `python -m compileall src main.py` —— 确保所有模块能正确解析。
- 运行功能需先安装依赖并提供有效的 API 凭证，详见快速开始章节。

### 后续计划

- 根据需要配置更多爬虫来源或替代的标注服务。
- 引入自动化测试（例如基于桩的响应）以保护关键处理器。
- 当管线稳定后，可容器化 CLI 或接入编排服务/计划任务。

---

## English

A configurable, extensible pipeline for scraping app-store reviews, unifying and cleaning the data, running automated labeling with large language models, and producing stratified dataset splits ready for downstream ML workflows.

### Highlights

- **Configuration-driven**: all runtime options live in `config/config.yaml`; no hard-coded parameters in the Python sources.
- **Composable CLI**: `main.py` exposes modular commands (`crawl`, `merge`, `prepare-labeling`, `label`, `split`, `run-all`). Each stage accepts explicit input/output paths so you always know which artefact is consumed next—no fragile "latest file" heuristics.
- **Extensible abstractions**: crawlers, processors, and labelers share simple base interfaces, making it straightforward to plug in new data sources or AI models.
- **Robust labeling loop**: the Gemini labeler batches requests, validates outputs against strict schemas, and automatically re-labels any invalid samples.
- **Production-ready ergonomics**: central logging, dependency declaration, deterministic filenames with timestamps, and a clearly defined repository layout.

### Repository Layout

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

### Getting Started

1. **Install dependencies**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate         # PowerShell on Windows
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

### Configuration Reference (`config/config.yaml`)

#### `paths`
Controls where generated artefacts and logs reside. Paths may be relative to project root or absolute. All directories are created on demand.

#### `scraping`
Two optional crawler blocks (`google_play`, `app_store`). Toggle each via `enabled`. Provide app IDs, locale/country, and desired review counts. App Store crawling also supports `request_delay` (seconds) and an optional `max_pages` safeguard.

#### `merging`
Defines the merged CSV filename pattern (must include `{timestamp}`) and the encoding used when reading/writing reviews.

#### `cleaning`
Text normalisation before labeling: minimum character requirements, emoji stripping toggle, and other heuristics. Produces an unlabeled JSON array ready for annotation.

#### `labeling`
- `provider`: currently `gemini` (hook for future providers).
- `gemini`: environment variable name, model ID, batching, retry/timeout policy, and validation loop settings.

The Gemini implementation loads `.env`, calls the Google GenAI client, validates outputs, and re-labels invalid samples until all pass or the configured round limit is reached.

#### `splitting`
Controls the stratified train/test split: `test_size`, `random_state`, and the column used for stratification (default `primary`).

#### `logging`
Standard logging level, format string, and log file location. A rotating file handler (5 MB × 3 backups) is configured in addition to console output.

### CLI Commands

| Command | Purpose | Key options |
|---------|---------|-------------|
| `crawl` | Run enabled crawlers and store raw CSVs | `--timestamp` overrides the timestamp used in filenames |
| `merge` | Combine one or both platform CSVs into the unified schema | `--google-csv`, `--app-store-csv`, `--timestamp` |
| `prepare-labeling` | Clean merged CSV and emit unlabeled JSON | `--merged-csv`, `--timestamp` |
| `label` | Annotate unlabeled JSON and optionally run validation/fixing | `--unlabeled-json`, `--timestamp`, `--skip-validation` |
| `split` | Produce stratified train/test JSON sets | `--labeled-json`, `--timestamp` |
| `run-all` | Execute the full pipeline using one shared timestamp | (inherits CLI config option only) |

All commands respect the `--config` option to point at a different YAML file.

### Extensibility Notes

- **Adding a crawler**: implement `BaseCrawler.fetch()` in a new class under `src/review_pipeline/crawlers/`, register its configuration block in `config/config.yaml`, and wire it inside `ReviewPipeline.run_crawl`.
- **Adding a labeler**: subclass `BaseLabeler`, provide `annotate` + `validate`, expose configuration via `LabelingConfig`, and update `LabelingWorkflow.__post_init__` with the new provider key.
- **Custom processors**: follow the structure in `processors/`—encapsulate the logic behind a simple method and orchestrate it through `pipeline/orchestrator.py` so the CLI automatically benefits.

### Logs & Artefacts

- Logs land in `logs/pipeline.log` (rotating). Adjust format/level in the config file or tail the console output for quick feedback.
- Generated datasets live under `data/`, split into `raw/`, `processed/`, `labeling/`, and `splits/`. The `.gitkeep` placeholders keep the folders in Git while ignoring actual artefacts.

### Legacy Scripts

The original monolithic notebooks/scripts were moved to `legacy_scripts/` for reference. They are no longer executed by the new pipeline but can serve as historical context while transitioning.

### Verification

- `python -m compileall src main.py` — ensures all modules parse correctly.
- Functional runs require the dependencies installed and valid API credentials; see the quick start instructions above.

### Next Steps

- Configure additional crawler sources or alternative labeling providers as needed.
- Integrate automated tests (e.g., fixtures with stubbed responses) to guard critical processors.
- Containerise the CLI or wire into an orchestration service/cron once the pipeline stabilises.
