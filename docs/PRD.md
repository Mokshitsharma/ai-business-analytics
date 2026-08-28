# Product Requirements Document — AI Business Analytics System

**Status:** Draft · **Owner:** Product · **Last updated:** 2026-08-28
**Source of truth:** derived from the current codebase (`core/`, `app/`, `api/`, `llm/`, `reporting/`).

---

## 1. Summary

The AI Business Analytics System lets a non-technical business user upload a
tabular dataset (CSV / Excel / JSON) and receive, with no configuration, a full
automated machine-learning analysis: data cleaning, exploratory data analysis
(EDA), automatic model training, SHAP explainability, rule-based business
insights, and an LLM-written executive summary — packaged as a downloadable HTML
and PDF report.

Today the product ships in two forms:

| Surface | Entry point | State |
|---|---|---|
| CLI | `run.py --file <path> --target <col>` | Working, committed |
| Web app (Streamlit) | `streamlit run app/main.py` | Working, committed |
| HTTP API (FastAPI) | `api/` | In progress, uncommitted, not wired |

This PRD describes the product as a whole and the target state the API work is
moving toward: a hosted, multi-tenant, plan-gated web service.

---

## 2. Goals & non-goals

### Goals
- **G1** — One-click analysis: upload → report, zero ML knowledge required.
- **G2** — Automatic problem detection: classification vs. regression chosen for
  the user from the target column.
- **G3** — Explainability by default: every model comes with global and local
  SHAP feature attributions.
- **G4** — Plain-language output: an executive summary and insights written for
  business readers, not data scientists.
- **G5** — Robustness on messy, small, real-world data: the pipeline must
  degrade gracefully rather than crash (missing values, tiny datasets, SHAP
  failures, LLM outage).
- **G6** — Tiered SaaS packaging: free / starter / pro plans gate file size, row
  count, monthly usage, PDF export, SHAP access, and AI summary.
- **G7** — Async job model: uploads return immediately; the client polls for
  progress and results.

### Non-goals (current phase)
- No deep learning, time-series forecasting models, or AutoML hyper-parameter
  search beyond model-family selection.
- No data-warehouse / database connectors — file upload only.
- No collaborative workspaces, dashboards that persist across sessions, or
  scheduled/recurring analyses.
- No fine-grained RBAC; "plan" is the only authorization axis.
- No model deployment / serving of the trained model back to the user.

---

## 3. Users & personas

| Persona | Needs | How the product serves them |
|---|---|---|
| **Business analyst / ops manager** (primary) | Understand what drives a KPI, get a shareable report | Upload dataset, pick KPI as target, download report |
| **Founder / exec** | Fast, jargon-free read on a dataset | Executive summary + insights sections |
| **Data-savvy operator** | Sanity-check model quality and feature importance | Metrics block, SHAP global/local sections, HTML report |
| **Developer integrator** (target state) | Programmatic analysis in their own product | REST API: `POST /upload`, poll `/jobs/{id}/status`, fetch `/jobs/{id}/result` |

---

## 4. User stories

1. As an analyst, I upload a CSV and select the target column so that I get a
   model predicting that column without writing code.
2. As an analyst, I see a progress indicator while the analysis runs so that I
   know it is working and roughly how long is left.
3. As an exec, I read a one-paragraph executive summary plus bulleted
   recommendations so that I can act without reading charts.
4. As an analyst, I download an HTML report to share internally and a PDF for
   attaching to a deck.
5. As a free-tier user, I am told clearly when my file exceeds the row/size
   limit and which plan removes the limit.
6. As a paid user, I get SHAP explanations and the AI-written summary unlocked.
7. As a developer, I call the API with a bearer token whose `plan` claim
   determines my limits.
8. As any user, if the LLM is unavailable I still get a structured fallback
   summary instead of an error.

---

## 5. Functional requirements

### 5.1 Ingestion
- **FR-1** Accept `.csv`, `.xlsx`, `.xls`, `.json` (`api/services/file_handler.py`,
  `utils/file_handler.py`). Streamlit currently accepts csv/xlsx/xls only.
- **FR-2** Reject unsupported extensions, empty files, and files over the
  plan's `max_file_size_mb` with a 400 and a human-readable message.
- **FR-3** Target column is user-selected; if omitted via API, default to the
  last column. Error if the named column is absent.

### 5.2 Analysis pipeline (`core/pipeline.py`, `api/services/job_runner.py`)
- **FR-4 Clean** — drop duplicate rows; detect column type
  (numerical / categorical / datetime / text via unique-ratio heuristic);
  impute missing values (median / mode / forward-fill / `"unknown"`); coerce
  dtypes.
- **FR-5 EDA** — summary statistics, correlation matrix + high-correlation
  pairs (|r| > 0.7), per-column distribution moments (mean/median/std/skew/
  kurtosis), datetime-based trend deltas, data-quality report.
- **FR-6 Feature engineering** — split X/y; `StandardScaler` on numerics,
  `OneHotEncoder(handle_unknown="ignore")` on categoricals via a
  `ColumnTransformer`; emit named feature columns.
- **FR-7 Model training** — auto-detect task (`object` dtype or ≤ 10 unique
  values ⇒ classification, else regression); train
  `RandomForestClassifier` / `RandomForestRegressor` (100 trees, seed 42);
  80/20 holdout; report accuracy + weighted F1 (classification) or RMSE + R²
  (regression); add cross-validation score using a **safe CV** that reduces
  folds for small/imbalanced data and returns `None` rather than crashing.
- **FR-8 Explainability** — SHAP global mean-|value| importance per feature and
  local attributions for up to 5 rows, computed on a sample of ≤ 100 rows;
  multiclass shapes handled; failure is caught and recorded as
  `{"error": ...}` without failing the job.
- **FR-9 Insights** — rule-based: rolling-window trend direction per numeric
  column, IQR-based anomaly counts, categorical-segment high/low comparisons,
  prediction distribution summary.
- **FR-10 Report assembly** — combine EDA + metrics + insights + explanations;
  generate an LLM executive summary from a structured prompt; on any LLM error
  fall back to a deterministic text summary.
- **FR-11 Report rendering** — HTML via Jinja2 template
  (`reporting/templates/report.html`); PDF via ReportLab. Written to
  `data/outputs/` (CLI/Streamlit) or `data/outputs/<job_id>/` (API).

### 5.3 Async jobs & delivery (API target)
- **FR-12** `POST /upload` validates, creates a job, saves the file, starts a
  background worker thread, and returns `{job_id, status:"queued", poll_url}`.
- **FR-13** Job status progresses through:
  `queued → cleaning → analyzing → modeling → explaining →
  generating_insights → generating_report → complete` (or `failed`), each
  mapped to a percentage in `api/job_store.py`.
- **FR-14** `GET /jobs/{id}/status` returns status, progress, error, timestamps.
- **FR-15** `GET /jobs/{id}/result` returns the full report dict once complete;
  locked sections are stripped per plan (SHAP, AI summary).
- **FR-16** `GET /jobs/{id}/report/html` and `.../report/pdf` stream the files;
  PDF is 403 for plans without `pdf_report`.
- **FR-17** `GET /health` reports environment and import health of each pipeline
  module.

### 5.4 Plans & limits (`api/services/plan_guard.py`)
- **FR-18** Enforce per-plan `max_file_size_mb`, `max_rows`, `pdf_report`,
  `shap_access`, `ai_summary`. `analyses_per_month` is defined but **not yet
  enforced** (no usage counter).
- **FR-19** Plan resolution: non-production ⇒ everyone is `pro`; production ⇒
  `plan` claim from a verified HS256 bearer JWT, else `free`.

| Limit | free | starter | pro |
|---|---|---|---|
| Max file size | 5 MB | 50 MB | 500 MB |
| Max rows | 1,000 | 50,000 | 500,000 |
| Analyses / month | 1 | 10 | unlimited |
| PDF report | ✗ | ✓ | ✓ |
| SHAP access | ✗ | ✓ | ✓ |
| AI summary | ✗ | ✓ | ✓ |

---

## 6. Non-functional requirements

- **NFR-1 Reliability** — a single bad dataset must never crash the process;
  `run_analysis_job` catches everything and records a `failed` job.
- **NFR-2 Latency** — typical analysis target ≈ 45 s (value surfaced to the
  client as `estimated_seconds`). No hard SLA yet.
- **NFR-3 Concurrency** — jobs run in daemon threads; job store and cache are
  thread-safe (`threading.Lock`). No multi-process / multi-node support yet.
- **NFR-4 Statelessness of results** — job state and cache are in-memory and
  lost on restart; report files persist on local disk only.
- **NFR-5 Security** — API keys and `JWT_SECRET` from environment; uploads
  confined to `data/uploads/<job_id>/`; no auth on read endpoints beyond plan
  gating (job IDs are unguessable UUID4).
- **NFR-6 Privacy** — uploaded business data and generated reports are stored
  unencrypted on local disk; retention/cleanup policy is TBD.
- **NFR-7 Observability** — stdout logging via `utils/logger.py`; no metrics or
  tracing yet.
- **NFR-8 Portability** — pure-Python stack; PDF uses ReportLab (no headless
  browser / system libs).

---

## 7. Success metrics

- Time-to-first-report from upload (target p50 < 60 s for < 50k rows).
- Job success rate (completed / total) ≥ 95%.
- LLM-summary success rate (non-fallback) ≥ 90% when a key is configured.
- Free→paid conversion on limit-exceeded events (target-state metric).

---

## 8. Open questions / risks

1. **No persistence** — restart loses all jobs. Needs a datastore before hosting.
2. **API not assembled** — no `api/main.py`, no router registration, FastAPI /
   uvicorn / python-multipart / PyJWT absent from `requirements.txt`.
3. **Usage metering missing** — `analyses_per_month` unenforceable without a
   per-user counter and identity.
4. **No real user/auth system** — only a JWT `plan` claim is consumed; no
   issuance, signup, billing, or account store.
5. **Threads not a queue** — background threads don't survive deploys, don't
   retry, and share the web process's resources.
6. **Model scope** — RandomForest only; no calibration, class-imbalance
   handling, or leakage checks beyond the target split.
7. **Report file growth** — `data/outputs/<job_id>/` is never garbage-collected.
8. **Streamlit vs API divergence** — Streamlit calls `core/pipeline.py`
   directly and ignores plans; API path is a parallel implementation in
   `job_runner.py`.
