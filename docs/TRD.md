# Technical Requirements Document — AI Business Analytics System

**Status:** Draft · **Last updated:** 2026-08-28
**Companion docs:** [PRD](./PRD.md) · [Architecture](./ARCHITECTURE.md) ·
[App Flow](./APPFLOW.md) · [Backend Schema](./BACKEND_SCHEMA.md) ·
[Implementation Plan](./IMPLEMENTATION_PLAN.md)

---

## 1. Scope

This document specifies the technical implementation of the system: languages,
libraries, module contracts, data shapes, interfaces, configuration, and the
concrete gaps between the current code and the target hosted service.

---

## 2. Technology stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.10+ | f-strings, `removeprefix`, `dict` merge used |
| Data | pandas, numpy | core dataframe operations |
| ML | scikit-learn | RandomForest, ColumnTransformer, StratifiedKFold |
| Explainability | shap | `shap.Explainer`, `check_additivity=False` |
| LLM | google-generativeai | model `gemini-flash-latest`, `temperature=0.3` |
| Templating | jinja2 | HTML report |
| PDF | reportlab | `SimpleDocTemplate` + Platypus flowables |
| Web app | streamlit | `app/main.py` |
| HTTP API | fastapi (implied) | `api/` routers — **not in requirements.txt** |
| Config | python-dotenv | `.env` via `find_dotenv()` |
| Excel | openpyxl | `pd.read_excel` engine |
| Auth (target) | PyJWT (`jwt`) | imported in `plan_guard.py`, not declared |

### 2.1 Dependency gaps to close
`requirements.txt` currently lists: pandas, numpy, scikit-learn, shap, jinja2,
reportlab, streamlit, google-generativeai, python-dotenv, openpyxl.

Missing for the API path: **fastapi**, **uvicorn[standard]**, **python-multipart**
(for `UploadFile`/`Form`), **PyJWT**. Pin versions and split into
`requirements.txt` (runtime) + `requirements-dev.txt` (pytest, ruff, etc.).

---

## 3. Repository layout

```
ai_business_analytics/
├── run.py                     # CLI entrypoint
├── configs/
│   ├── settings.py            # env-driven config
│   └── model_config.yaml      # EMPTY — reserved
├── core/
│   ├── pipeline.py            # Pipeline orchestrator (CLI/Streamlit)
│   ├── preprocessing/
│   │   ├── cleaner.py         # DataCleaner (implemented)
│   │   ├── transformer.py     # EMPTY
│   │   └── validator.py       # EMPTY
│   ├── eda/
│   │   ├── analyzer.py        # EDAAnalyzer (implemented)
│   │   ├── stats.py           # EMPTY
│   │   └── visualizer.py      # EMPTY
│   ├── features/
│   │   ├── engineer.py        # FeatureEngineer (implemented)
│   │   └── encoder.py         # EMPTY
│   ├── models/
│   │   ├── trainer.py         # ModelTrainer (implemented)
│   │   ├── evaluator.py       # ModelEvaluator (implemented, unused by pipeline)
│   │   ├── selector.py        # EMPTY
│   │   └── registry.py        # EMPTY
│   ├── xai/
│   │   ├── shap_explainer.py  # ShapExplainer (implemented)
│   │   └── importance.py      # EMPTY
│   └── insights/
│       ├── generator.py       # InsightGenerator (implemented)
│       ├── anomaly.py         # EMPTY
│       ├── segmentation.py    # EMPTY
│       └── trends.py          # EMPTY
├── llm/
│   ├── client.py             # LLMClient (Gemini)
│   ├── prompt_templates.py   # build_summary_prompt
│   ├── summarizer.py         # LLMSummarizer + fallback
│   └── recommender.py        # EMPTY
├── reporting/
│   ├── report_builder.py     # ReportBuilder
│   ├── html_generator.py     # HTMLReportGenerator (Jinja2)
│   ├── pdf_generator.py      # PDFReportGenerator (ReportLab)
│   └── templates/
│       ├── report.html
│       └── styles.css
├── api/
│   ├── main.py              # FastAPI app: routers, CORS, error envelope, static mount
│   ├── static/index.html   # single-page browser UI (vanilla JS)
│   ├── cache.py              # SimpleCache (TTL, thread-safe)
│   ├── job_store.py          # JobStore + module-level singleton
│   ├── routers/
│   │   ├── health.py         # GET /health
│   │   ├── upload.py         # POST /upload
│   │   ├── jobs.py           # GET /jobs/{id}/status | /result
│   │   └── report.py         # GET /jobs/{id}/report/html | /pdf
│   └── services/
│       ├── file_handler.py   # validate_file, save_upload
│       ├── job_runner.py     # run_analysis_job (background)
│       └── plan_guard.py     # PLAN_LIMITS, get_plan, check_row_limit
├── app/
│   ├── main.py               # Streamlit app (implemented)
│   ├── pages/                # dashboard/insights/reports/upload — EMPTY
│   └── components/           # charts/tables — EMPTY
├── utils/
│   ├── file_handler.py       # load_dataset (csv/xlsx/xls/json)
│   ├── helpers.py            # formatting helpers (Indian digit grouping etc.)
│   ├── logger.py             # get_logger
│   └── cv.py                 # get_safe_cv
├── tests/                    # test_pipeline / test_models / test_preprocessing — EMPTY
├── data/outputs/             # generated reports (committed samples present)
└── notebooks/experimentation.ipynb  # EMPTY
```

---

## 4. Module contracts

### 4.1 `utils/file_handler.load_dataset(path: str) -> pd.DataFrame`
Dispatches on extension: `csv → read_csv`, `xlsx|xls → read_excel`,
`json → read_json`. Raises `ValueError` on anything else.

### 4.2 `core.preprocessing.cleaner.DataCleaner`
- `clean(df) -> df` — pure, operates on a copy.
- Column-type heuristic: numeric dtype ⇒ `numerical`; datetime dtype ⇒
  `datetime`; else unique-ratio `< 0.05` ⇒ `categorical`, otherwise `text`.
- Imputation: numerical → median; categorical → mode[0]; datetime → `ffill`;
  text → `"unknown"`.
- **Known issue:** `df.fillna(method="ffill")` is deprecated in pandas ≥ 2.1;
  switch to `df.ffill()`.

### 4.3 `core.eda.analyzer.EDAAnalyzer.analyze(df) -> dict`
Keys: `summary_stats`, `correlations` (`correlation_matrix`,
`high_correlations` for |r| > 0.7), `distributions` (per numeric col moments),
`trends` (Δ of 5-window rolling mean over each datetime col), `data_quality`
(`missing_values`, `duplicate_rows`, `num_rows`, `num_columns`).
Output is JSON-serialisable via `float()`/`int()` casts.

### 4.4 `core.features.engineer.FeatureEngineer.transform(df, target_column) -> (X, y)`
- Raises `ValueError` if `target_column` absent.
- `y = df[target]`, `X = df.drop(target)`.
- `ColumnTransformer`: `StandardScaler` on `select_dtypes(number)`,
  `OneHotEncoder(handle_unknown="ignore")` on the rest.
- Returns `X` as a named `DataFrame` (numeric names + `get_feature_names_out`),
  same index as input.
- **Contract note:** encoder is not persisted for inference; datetime columns
  fall into the "non-numeric" bucket and will be one-hot encoded — usually
  undesirable. Datetime handling is a known gap.

### 4.5 `core.models.trainer.ModelTrainer.train(X, y) -> dict`
Returns `{"model", "metrics", "task_type"}`.
- `detect_task`: `y.dtype == object` or `y.nunique() <= 10` ⇒ `classification`.
- 80/20 `train_test_split(random_state=42)` — **not stratified**.
- Classification metrics: `accuracy`, `f1_score` (weighted).
  Regression metrics: `rmse` (`sqrt(MSE)`), `r2_score`.
- `cv_score`: mean of `cross_val_score` with `get_cv(y)`; `get_cv` returns
  `None` when `min_class < 2` or `n_splits < 2`; regression `y` passed to
  `StratifiedKFold` will typically raise and yield `cv_score = None`.

### 4.6 `core.xai.shap_explainer.ShapExplainer.explain(model, X) -> dict`
- Samples ≤ `sample_size` (100) rows, seed 42.
- `shap.Explainer(model, X_sample)`, called with `check_additivity=False`.
- `global_importance`: mean over samples of `|shap|` (multiclass averaged over
  class axis) → `{feature: float}`.
- `local_explanations`: up to 5 rows, each `{prediction_index, feature_values,
  shap_values}`.
- Caller must wrap in `try/except` (pipeline and job_runner both do).

### 4.7 `core.insights.generator.InsightGenerator.generate(df, predictions) -> dict`
Keys: `trends` (list[str]), `anomalies` (list[str], IQR × 1.5),
`segments` (list[str], groupby-mean idxmax/idxmin per cat×num pair),
`predictions` (`mean/min/max_prediction`).
- **Scaling concern:** `segments` is O(n_categorical × n_numeric) group-bys; can
  explode on wide frames.

### 4.8 `llm` package
- `LLMClient(model=None)` — reads `GOOGLE_API_KEY`, raises `ValueError` if
  missing; `generate(prompt) -> str` with `temperature=0.3`.
- `build_summary_prompt(context)` — context keys `metrics`, `insights`, `eda`;
  trims EDA to `data_quality` + `high_correlations` to bound prompt size.
- `LLMSummarizer.summarize(context) -> str` — try LLM, `except Exception` ⇒
  `_fallback_summary` (deterministic text). Note: constructor calls
  `LLMClient()`, so a missing key raises at `ReportBuilder.__init__` time, not
  inside the guarded `summarize`. **Fix:** lazy-init the client or catch in
  `summarize`.

### 4.9 `reporting`
- `ReportBuilder.build(eda_results, metrics, insights, explanations) -> dict`
  with keys `executive_summary`, `metrics`, `insights`, `eda`, `explanations`.
- `HTMLReportGenerator.generate(report_data, output_path="data/outputs/report.html") -> path`
  — Jinja2, `autoescape=True`.
- `PDFReportGenerator.generate(report_data, output_path="data/outputs/report.pdf") -> path`
  — requires `executive_summary`, `metrics`, `insights` keys; iterates insight
  sections; **`KeyError` if `executive_summary` is `None`** (plan-locked case
  handled only at API result layer, not in the generator).

### 4.10 `api` package
- `SimpleCache` — `get/set/delete`, per-key TTL, `threading.Lock`. Currently
  **not referenced** by any router.
- `JobStore` — `create_job`, `update_status`, `get_job` (returns a copy),
  `set_result`; `PROGRESS_BY_STATUS` maps status → %. Module singleton
  `job_store`. Note `update_status` treats `"failed"` specially but callers
  pass `status="failed"` while `PROGRESS_BY_STATUS` has no `failed` key
  (handled by the branch).
- `plan_guard.PLAN_LIMITS` — see PRD §5.4 table. `get_plan(request)` and
  `check_row_limit(df, plan)` (raises `HTTPException(403)` with upgrade hint).
- `file_handler.validate_file(file, plan)` — extension allowlist
  `{.csv,.xlsx,.xls,.json}`, size via `seek/tell`, empty-file check.
  `save_upload(file, job_id) -> Path` under `UPLOADS_DIR/<job_id>/`.
- `job_runner.run_analysis_job(job_id, file_path, target_column, plan)` —
  never raises; drives `job_store` through every stage; writes reports to
  `data/outputs/<job_id>/`; result dict = report dict + `report_html_path`,
  `report_pdf_path`, `row_count`, `column_count`, `target_column`, `task_type`.

---

## 5. HTTP API specification (target)

Base URL: `/` (no version prefix today — **add `/v1`**).

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | `/health` | none | — | `{status, environment, pipeline_modules{...bool}}` |
| POST | `/upload` | Bearer (prod) | multipart: `file`, `target_column?`, `plan?` | `202 {job_id, status:"queued", message, estimated_seconds, poll_url}` |
| GET | `/jobs/{job_id}/status` | none¹ | — | `{job_id, status, progress, error, created_at, completed_at}` or `404` |
| GET | `/jobs/{job_id}/result` | none¹ | — | full report dict (plan-stripped) or `{status, progress, message}` if not done, or `404` |
| GET | `/jobs/{job_id}/report/html` | none¹ | — | `text/html` file or `404`/`409` |
| GET | `/jobs/{job_id}/report/pdf` | none¹ | — | `application/pdf` or `403` (plan) / `404` / `409` |

¹ Currently unauthenticated; job ID is an unguessable UUID4. Target state:
require the same bearer token and check ownership.

### 5.1 `plan` handling
- Request form field `plan` is trusted as-is by `/upload` today (dev
  convenience). Target state: **ignore the form field**, derive plan from the
  verified JWT via `get_plan(request)` in every router.
- `get_plan`: non-prod ⇒ `"pro"`; prod ⇒ JWT `plan` claim (HS256, `JWT_SECRET`),
  fallback `"free"`.

### 5.2 Error model
FastAPI `HTTPException`; `detail` is sometimes a string, sometimes a dict
(`{error, limit, your_rows, upgrade_to}` / `{error, upgrade_to}`).
**Requirement:** standardise on `{error: str, code: str, ...context}` and a
consistent HTTP status map.

### 5.3 Job status machine
```
queued(0) → cleaning(10) → analyzing(30) → modeling(50) → explaining(65)
          → generating_insights(80) → generating_report(90) → complete(100)
   (any stage on error) ----------------------------------> failed
                                          (error recorded, completed_at set)
```

---

## 6. Configuration (`configs/settings.py`)

| Env var | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | gates `get_plan` behaviour |
| `GOOGLE_API_KEY` | `""` | Gemini auth; empty ⇒ summary falls back |
| `JWT_SECRET` | `""` | HS256 verification for plan claims |
| `MAX_UPLOAD_SIZE_MB` | `500` | declared, **not currently read** by validators (plan limits used instead) |
| `DATA_DIR` | `data/` | base data dir |
| `OUTPUTS_DIR` | `data/outputs/` | report output (used by generators' defaults indirectly) |
| `UPLOADS_DIR` | `data/uploads/` | per-job upload dir |

`model_config.yaml` is empty and reserved for future model-family / hyperparam
configuration.

---

## 7. Cross-cutting requirements

- **TR-1 Determinism** — all random operations seed `42`.
- **TR-2 JSON-safety** — every pipeline output must be JSON-serialisable
  (numpy scalars cast to `float`/`int`). Enforce with a serialisation test.
- **TR-3 Graceful degradation** — SHAP failure, LLM failure, tiny-data CV all
  degrade, never raise to the user.
- **TR-4 Encoding** — force UTF-8 stdout (`run.py`); templates write UTF-8.
- **TR-5 Isolation** — per-job upload + output directories keyed by UUID4.
- **TR-6 Thread-safety** — shared mutable state (`JobStore`, `SimpleCache`)
  guarded by locks; pipeline objects are per-job instances.
- **TR-7 Logging** — module loggers via `utils/logger.get_logger`; no secrets
  in logs (JWT failures log the exception message only).

---

## 8. Known technical debt / required fixes

> **Update 2026-08-28:** items 1, 2, 4, 6, 7 are now resolved — `api/main.py`
> assembles the app, deps are declared, `/upload` derives the plan via
> `get_plan()`, `LLMSummarizer` is lazy + timeout-guarded, and the deprecated
> `fillna(method=...)` call is gone. Also added: `utils/serialization.to_json_safe`
> (NaN/inf-safe API responses), datetime/high-cardinality handling in
> `FeatureEngineer`, and a non-numeric-prediction branch in `InsightGenerator`.

| # | Item | Location | Priority |
|---|---|---|---|
| 1 | No FastAPI app assembly / entrypoint | `api/` (missing `main.py`) | P0 |
| 2 | FastAPI/uvicorn/python-multipart/PyJWT not declared | `requirements.txt` | P0 |
| 3 | In-memory job & cache lost on restart | `api/job_store.py`, `api/cache.py` | P0 for hosting |
| 4 | `plan` accepted from client form field | `api/routers/upload.py` | P0 (security) |
| 5 | Read endpoints unauthenticated, no ownership check | `api/routers/*` | P1 |
| 6 | `LLMClient()` constructed eagerly in `ReportBuilder` | `llm/summarizer.py` | P1 |
| 7 | `fillna(method="ffill")` deprecated | `core/preprocessing/cleaner.py` | P1 |
| 8 | PDF generator `KeyError` when summary is `None`/missing | `reporting/pdf_generator.py` | P1 |
| 9 | `train_test_split` not stratified for classification | `core/models/trainer.py` | P2 |
| 10 | Datetime columns one-hot encoded as categoricals | `core/features/engineer.py` | P2 |
| 11 | `analyses_per_month` defined but unenforced | `api/services/plan_guard.py` | P2 |
| 12 | Zero test coverage (all test files empty) | `tests/` | P1 |
| 13 | `data/outputs/<job_id>/` never cleaned up | `api/services/job_runner.py` | P2 |
| 14 | Streamlit path bypasses plan gating entirely | `app/main.py` | P2 |
| 15 | `SimpleCache` implemented but unused | `api/cache.py` | P3 |
