# Architecture — AI Business Analytics System

**Status:** Draft · **Last updated:** 2026-08-28
**Companion docs:** [PRD](./PRD.md) · [TRD](./TRD.md) · [App Flow](./APPFLOW.md) ·
[Backend Schema](./BACKEND_SCHEMA.md) · [Implementation Plan](./IMPLEMENTATION_PLAN.md)

---

## 1. Architectural overview

The system is a **layered pipeline application** with two thin delivery
surfaces (CLI, Streamlit) and one in-progress surface (HTTP API). The heavy
lifting lives in a provider-agnostic `core/` package that turns a DataFrame into
a structured report dict; delivery surfaces only handle I/O, orchestration, and
packaging.

```
                        ┌──────────────────────────────────────────────┐
   Delivery surfaces    │  CLI (run.py)   Streamlit (app/main.py)       │
                        │                 HTTP API (api/ — in progress) │
                        └───────────────┬──────────────────────────────┘
                                        │ DataFrame + target column
                        ┌───────────────▼──────────────────────────────┐
   Orchestration        │  core/pipeline.py  |  api/services/job_runner │
                        └───────────────┬──────────────────────────────┘
                                        │ sequential stages
        ┌───────────────┬───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼               ▼
   preprocessing/    eda/          features/        models/          xai/
   DataCleaner    EDAAnalyzer   FeatureEngineer  ModelTrainer    ShapExplainer
        │               │               │               │               │
        └───────────────┴───────────────┴───────┬───────┴───────────────┘
                                                ▼
                                        insights/InsightGenerator
                                                │
                                                ▼
                                     reporting/ReportBuilder
                                                │  context {eda, metrics, insights}
                                                ▼
                                     llm/LLMSummarizer ──► Gemini (or fallback)
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        ▼                                               ▼
              reporting/HTMLReportGenerator                 reporting/PDFReportGenerator
                     (Jinja2)                                     (ReportLab)
                        │                                               │
                        └───────────────────────┬───────────────────────┘
                                                ▼
                                      data/outputs/[<job_id>/]report.{html,pdf}
```

---

## 2. Layers & responsibilities

| Layer | Packages | Responsibility | Depends on |
|---|---|---|---|
| **Delivery** | `run.py`, `app/`, `api/routers/` | Accept input, auth/plan gating, return output/files | Orchestration |
| **Orchestration** | `core/pipeline.py`, `api/services/job_runner.py`, `api/job_store.py` | Sequence stages, track progress, catch errors | Domain, Reporting |
| **Domain (core)** | `core/preprocessing`, `core/eda`, `core/features`, `core/models`, `core/xai`, `core/insights` | Pure data → analysis transforms | pandas/sklearn/shap only |
| **Reporting** | `reporting/` | Assemble report dict, render HTML/PDF | LLM, templates |
| **LLM** | `llm/` | Prompt construction, Gemini call, deterministic fallback | google-generativeai |
| **Platform / shared** | `configs/`, `utils/`, `api/cache.py`, `api/services/plan_guard.py` | Config, logging, file IO, formatting, plan limits, caching | stdlib |

**Dependency rule:** delivery → orchestration → domain/reporting → llm/platform.
The domain layer never imports from delivery, reporting, or llm.

---

## 3. Two orchestration paths (current reality)

There are **two parallel orchestrators** implementing the same 7 stages:

| | `core/pipeline.py` (`Pipeline`) | `api/services/job_runner.py` (`run_analysis_job`) |
|---|---|---|
| Used by | CLI, Streamlit | HTTP API |
| Style | synchronous, returns dict | background thread, mutates `JobStore` |
| Progress | none | `job_store.update_status` per stage |
| Error handling | SHAP guarded; rest propagates | everything caught → `failed` job |
| Plan gating | none | `check_row_limit`, result stripping |
| Output path | `data/outputs/report.{html,pdf}` | `data/outputs/<job_id>/report.{html,pdf}` |

**Target state:** collapse to one orchestrator. `Pipeline` becomes the single
stage engine, accepting an optional `progress_callback` and `plan`; `job_runner`
becomes a thin adapter that wires the callback to `JobStore` and applies plan
stripping. See [Implementation Plan](./IMPLEMENTATION_PLAN.md) Phase 2.

---

## 4. Component detail

### 4.1 Domain pipeline stages
Each stage is a class with a single public method, stateless between runs
(instantiated per job), and returns plain Python / JSON-safe structures.

1. **`DataCleaner.clean(df) → df`** — dedupe, heuristic type detection,
   impute, dtype coercion.
2. **`EDAAnalyzer.analyze(df) → dict`** — stats, correlations, distributions,
   datetime trends, data-quality.
3. **`FeatureEngineer.transform(df, target) → (X, y)`** — `ColumnTransformer`
   (`StandardScaler` + `OneHotEncoder`), named feature output.
4. **`ModelTrainer.train(X, y) → {model, metrics, task_type}`** — task
   auto-detect, RandomForest, holdout metrics, safe CV.
5. **`ShapExplainer.explain(model, X) → dict`** — sampled global + local SHAP;
   caller-guarded.
6. **`InsightGenerator.generate(df, predictions) → dict`** — rule-based trends,
   IQR anomalies, categorical segments, prediction summary.
7. **`ReportBuilder.build(...) → report dict`** — merges stage outputs, invokes
   `LLMSummarizer`.

### 4.2 Reporting & LLM
- `LLMSummarizer` builds a bounded prompt (EDA trimmed to data-quality +
  high-correlations), calls `LLMClient` (Gemini `gemini-flash-latest`,
  `temperature=0.3`), and on **any** exception returns `_fallback_summary`
  (deterministic text). This is the key resilience seam for LLM outages.
- `HTMLReportGenerator` — Jinja2 `FileSystemLoader("reporting/templates")`,
  `autoescape=True`, renders `report.html` + `styles.css`.
- `PDFReportGenerator` — ReportLab Platypus; no browser/system deps.

### 4.3 API platform components
- **`JobStore`** (in-memory dict + `Lock`) — the async job registry. Singleton
  `job_store`. Status→progress map is the single source of progress truth.
- **`SimpleCache`** (in-memory, TTL, `Lock`) — built, not yet wired; intended
  for caching results / expensive lookups.
- **`plan_guard`** — `PLAN_LIMITS` table + `get_plan(request)` (JWT in prod,
  `"pro"` in dev) + `check_row_limit`. Enforcement points: `validate_file`
  (size/type), `check_row_limit` (rows), result assembly (SHAP / AI summary),
  `report.py` (PDF).
- **`file_handler`** — extension allowlist, size check via `seek/tell`, per-job
  directory under `UPLOADS_DIR`.

---

## 5. Data flow & storage

| Artefact | Where it lives | Lifetime |
|---|---|---|
| Uploaded file | `data/uploads/<job_id>/<filename>` (disk) | until manual cleanup |
| Job record (status, progress, result dict) | `JobStore` (process memory) | until process restart |
| Report dict | inside the job record | same |
| Rendered HTML/PDF | `data/outputs/<job_id>/report.{html,pdf}` (disk) | until manual cleanup |
| Config / secrets | environment / `.env` | process lifetime |
| Cache entries | `SimpleCache` (process memory) | TTL then evicted |

**No database.** All structured state is process-local. This is the central
constraint blocking horizontal scaling and durable hosting.

---

## 6. Runtime & deployment model

### 6.1 Current
- CLI: one-shot process.
- Streamlit: single process, in-process pipeline execution (blocks the session
  spinner).
- API (once assembled): single uvicorn process; background work on
  `threading.Thread(daemon=True)` inside the web process.

### 6.2 Target (hosted)
```
            ┌── Load balancer / TLS ──┐
            ▼                         ▼
      API worker (uvicorn)     API worker (uvicorn)     ← stateless
            │                         │
            ├─────────► Postgres ◄─────┤   jobs, users, plans, usage
            ├─────────► Redis   ◄─────┤   cache, rate limits, queue broker
            └─────────► Object store ◄┘   uploads + rendered reports (S3-compatible)
                        ▲
                 Worker process(es)  ← Celery/RQ/Arq; runs the pipeline
```
- API workers become stateless: no in-memory `JobStore`, no daemon threads.
- Pipeline runs in a dedicated worker pool consuming a queue.
- `JobStore` → Postgres table; `SimpleCache` → Redis; disk paths → object store
  keys. See [Backend Schema](./BACKEND_SCHEMA.md).

---

## 7. Cross-cutting concerns

| Concern | Mechanism | Notes / gaps |
|---|---|---|
| Configuration | `configs/settings.py` + `.env` | `MAX_UPLOAD_SIZE_MB` unused; no schema validation |
| Auth / authz | JWT `plan` claim (`plan_guard`) | no issuance, no user identity, read endpoints open |
| Error handling | per-layer try/except; API `HTTPException` | `detail` shape inconsistent (str vs dict) |
| Resilience | SHAP + LLM + CV degrade gracefully | `LLMClient()` eager init in `ReportBuilder` can still raise |
| Determinism | seed 42 everywhere | — |
| Logging | `utils/logger.get_logger` → stdout | no request IDs / correlation, no metrics/tracing |
| Concurrency | `Lock` on shared stores; per-job objects | thread pool unbounded (one thread per upload) |
| Security | UUID4 job IDs, upload dir isolation | client-supplied `plan`, no ownership checks, plaintext-at-rest data |
| Testing | `tests/` scaffold present | all files empty |

---

## 8. Key architectural decisions (ADR summary)

| ID | Decision | Rationale | Consequence / revisit trigger |
|---|---|---|---|
| ADR-1 | Provider-agnostic `core/` returning plain dicts | Reusable across CLI/Streamlit/API; easy to test | Delivery layers must own packaging |
| ADR-2 | RandomForest as the only model family | Strong default, no tuning, SHAP-friendly | Revisit when regression R² or class imbalance is poor |
| ADR-3 | SHAP for explainability | Model-agnostic, well understood by stakeholders | Cost scales with data; mitigated by 100-row sample |
| ADR-4 | LLM summary with deterministic fallback | Product must not hard-depend on an external API | Fallback text is terse; acceptable |
| ADR-5 | ReportLab for PDF (not headless Chrome) | No system libraries, portable, cheap | PDF styling is basic vs the HTML template |
| ADR-6 | In-memory `JobStore` + daemon threads (v0) | Fastest path to a working async API | **Must replace** before hosting (ADR-7) |
| ADR-7 | (Target) Postgres + Redis + queue + object store | Durability, horizontal scale, real metering | Implementation Plan Phases 3–4 |
| ADR-8 | Plan tiers as the only authz axis | Matches SaaS packaging; simple | No org/team/RBAC until needed |
