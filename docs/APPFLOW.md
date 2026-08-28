# App Flow — AI Business Analytics System

**Status:** Draft · **Last updated:** 2026-08-28
**Companion docs:** [PRD](./PRD.md) · [TRD](./TRD.md) · [Architecture](./ARCHITECTURE.md) ·
[Backend Schema](./BACKEND_SCHEMA.md) · [Implementation Plan](./IMPLEMENTATION_PLAN.md)

This document traces every path a request takes through the system, for each
delivery surface.

---

## 1. Flow index

| # | Flow | Surface | Status |
|---|---|---|---|
| A | CLI single-shot analysis | `run.py` | Working |
| B | Streamlit interactive analysis | `app/main.py` | Working |
| C | API async analysis (happy path) | `api/` | Code present, unwired |
| D | API polling & result retrieval | `api/` | Code present, unwired |
| E | API report download (HTML/PDF) | `api/` | Code present, unwired |
| F | Plan gating & limit-exceeded | `api/services/plan_guard.py` | Code present |
| G | Failure & degradation paths | all | Working |
| H | Health check | `api/routers/health.py` | Code present |

---

## 2. Flow A — CLI single-shot analysis

```
$ python run.py --file sales.csv --target churn
```

1. `run.py:main()` reconfigures stdout to UTF-8, parses `--file`, `--target`.
2. `utils.file_handler.load_dataset(file)` → DataFrame (dispatch on extension;
   `ValueError` if unsupported → traceback, exit).
3. `Pipeline(config={}).run(df, target)`:
   1. `DataCleaner.clean(df)` — dedupe, type detect, impute, coerce.
   2. `EDAAnalyzer.analyze(df)` → `eda_results`.
   3. `FeatureEngineer.transform(df, target)` → `(X, y)`
      (`ValueError` if target missing → traceback, exit).
   4. `ModelTrainer.train(X, y)` → `{model, metrics, task_type}`;
      `metrics["task_type"]` set.
   5. `ShapExplainer.explain(model, X)` inside `try/except` →
      `explanations` or `{"error": ...}`.
   6. `model.predict(X)` → `predictions`; `InsightGenerator.generate(df, predictions)`.
   7. `ReportBuilder.build(...)`:
      - assembles `context = {eda, metrics, insights}`
      - `LLMSummarizer.summarize(context)` → Gemini call, or `_fallback_summary`
        on any exception
      - returns report dict `{executive_summary, metrics, insights, eda, explanations}`.
4. `HTMLReportGenerator.generate(report)` → `data/outputs/report.html`.
5. `PDFReportGenerator.generate(report)` → `data/outputs/report.pdf`.
6. Prints success + both paths.

**Failure modes:** unsupported file, missing target, empty/garbage data →
unhandled exception + non-zero exit. SHAP / LLM failures are swallowed.

---

## 3. Flow B — Streamlit interactive analysis

```
$ streamlit run app/main.py
```

1. Page renders: title, file uploader (`csv/xlsx/xls`).
2. **On upload:** `load_data(uploaded_file)` writes a `NamedTemporaryFile`,
   reads it with `pd.read_csv` / `pd.read_excel` → `(df, temp_path)`.
   Unsupported extension → `ValueError` → `st.error`.
3. Shows `df.head()` preview and a `selectbox` of columns for the target.
4. **On "Run Analysis":** spinner; `Pipeline(config={}).run(df, target_column)`
   (identical stage sequence to Flow A §3.3).
5. Renders `report_data`:
   - `st.write(executive_summary)`
   - `st.json(metrics)`
   - `st.json(insights)`
6. Generates HTML + PDF to `data/outputs/` and exposes two
   `st.download_button`s.
7. `finally:` deletes the temp upload file.

**Notes / gaps:** no plan gating (all features always on); pipeline runs
in-process and blocks the session; `data/outputs/report.{html,pdf}` is shared
across concurrent users (last write wins).

---

## 4. Flow C — API async analysis (happy path)

### Request
```
POST /upload
Content-Type: multipart/form-data
Authorization: Bearer <jwt>            # prod only
Fields: file=<binary>, target_column="churn", plan="starter"
```

### Sequence
```
Client        upload.py            file_handler       job_store        Thread(job_runner)
  │  POST /upload  │                    │                 │                    │
  │───────────────►│                    │                 │                    │
  │               │ validate_file(file, plan)             │                    │
  │               │───────────────────►│  ext allowlist   │                    │
  │               │                    │  size ≤ plan max  │                    │
  │               │                    │  not empty        │                    │
  │               │◄───────────────────│  ok / HTTPException(400)               │
  │               │ create_job(filename, target, plan)     │                    │
  │               │──────────────────────────────────────►│  job_id (uuid4)    │
  │               │                    │                 │  status=queued(0)   │
  │               │ save_upload(file, job_id)              │                    │
  │               │───────────────────►│  data/uploads/<job_id>/<filename>     │
  │               │ start daemon thread ─────────────────────────────────────►│
  │◄──────────────│ 202 {job_id, status:"queued", poll_url, estimated_seconds:45}
  │               │                    │                 │                    │
  │               │                    │        run_analysis_job(job_id, path, target, plan)
  │               │                    │                 │  load_dataset(path)  │
  │               │                    │                 │  check_row_limit(df, plan) ─► 403-style raise → failed
  │               │                    │                 │  target = target or df.columns[-1]
  │               │                    │                 │  update_status "cleaning"(10)     → DataCleaner
  │               │                    │                 │  update_status "analyzing"(30)    → EDAAnalyzer
  │               │                    │                 │  update_status "modeling"(50)     → FeatureEngineer + ModelTrainer
  │               │                    │                 │  update_status "explaining"(65)   → ShapExplainer (guarded)
  │               │                    │                 │  update_status "generating_insights"(80) → predict + InsightGenerator
  │               │                    │                 │  update_status "generating_report"(90)   → ReportBuilder (LLM/fallback)
  │               │                    │                 │  HTML + PDF → data/outputs/<job_id>/
  │               │                    │                 │  set_result(job_id, result)
  │               │                    │                 │  update_status "complete"(100)
```

### `result` dict (stored on the job)
```
{ ...report,                       # executive_summary, metrics, insights, eda, explanations
  report_html_path, report_pdf_path,
  row_count, column_count, target_column, task_type }
```

---

## 5. Flow D — API polling & result retrieval

```
GET /jobs/{job_id}/status
  → 404 if unknown
  → { job_id, status, progress, error, created_at, completed_at }

Client polls every ~2–3s until status == "complete" or "failed".

GET /jobs/{job_id}/result
  → 404 if unknown
  → if status != "complete":  { status, progress, message:"Not ready yet" }
  → if complete:  deepcopy(result), then PLAN STRIPPING:
       limits = PLAN_LIMITS[plan] (fallback "free")
       if not limits["shap_access"]:
           result["explanations"] = { locked:true, message:"Upgrade to Starter or Pro…" }
       if not limits["ai_summary"]:
           result["executive_summary"] = None
           result["executive_summary_locked"] = true
     → return result
```

---

## 6. Flow E — API report download

```
GET /jobs/{job_id}/report/html
  _get_completed_job: 404 if unknown, 409 if status != "complete"
  → FileResponse(result["report_html_path"], media_type="text/html", filename="report.html")

GET /jobs/{job_id}/report/pdf
  _get_completed_job (404 / 409)
  limits = PLAN_LIMITS[plan] (fallback "free")
  if not limits["pdf_report"]:
      → 403 { error:"PDF reports require a paid plan", upgrade_to:"starter" }
  → FileResponse(result["report_pdf_path"], media_type="application/pdf", filename="report.pdf")
```

---

## 7. Flow F — Plan gating decision points

| Check | Where | Free | Starter | Pro | On violation |
|---|---|---|---|---|---|
| Extension allowlist | `validate_file` | csv/xlsx/xls/json | same | same | 400 |
| File size | `validate_file` | ≤ 5 MB | ≤ 50 MB | ≤ 500 MB | 400 with plan hint |
| Empty file | `validate_file` | — | — | — | 400 |
| Row count | `check_row_limit` (in `job_runner`) | ≤ 1,000 | ≤ 50,000 | ≤ 500,000 | job → `failed`, error dict with `upgrade_to` |
| SHAP in result | `/jobs/{id}/result` | locked | unlocked | unlocked | `explanations` replaced with lock notice |
| AI summary in result | `/jobs/{id}/result` | locked | unlocked | unlocked | `executive_summary=None`, `_locked=true` |
| PDF download | `/jobs/{id}/report/pdf` | blocked | allowed | allowed | 403 with `upgrade_to` |
| Analyses / month | *(not implemented)* | 1 | 10 | ∞ | — |

**Plan resolution (`get_plan`)**: `ENVIRONMENT != "production"` ⇒ `"pro"`.
Production ⇒ decode `Bearer` JWT (HS256, `JWT_SECRET`), read `plan` claim;
missing/invalid token or unknown plan ⇒ `"free"`.
*Current `/upload` reads `plan` from the form field directly — see TRD §8 item 4.*

---

## 8. Flow G — Failure & degradation paths

| Failure | Detected in | Behaviour |
|---|---|---|
| Unsupported file type | `validate_file` / `load_dataset` | 400 (API) / `ValueError` (CLI, Streamlit `st.error`) |
| File too large / empty | `validate_file` | 400 with message |
| Row limit exceeded | `check_row_limit` | job `failed`, error surfaced via `/status` and `/result` |
| Target column missing | `job_runner` / `FeatureEngineer` | job `failed` (API) / `ValueError` (CLI) |
| SHAP computation error | `job_runner` / `pipeline` `try/except` | `explanations = {"error": ...}`, job continues, warning logged |
| LLM error / no API key at call time | `LLMSummarizer.summarize` `try/except` | `_fallback_summary` deterministic text |
| **LLM key missing at construction** | `ReportBuilder.__init__` → `LLMClient()` | **raises** — job `failed` (API) / traceback (CLI). Known bug, TRD §8 item 6 |
| Any other pipeline exception | `run_analysis_job` outer `try/except` | job `failed`, `_extract_error_message` normalises `HTTPException.detail`, error logged |
| Process restart | — | all jobs + cache lost; report files remain on disk but unreachable via API |

---

## 9. Flow H — Health check

```
GET /health
  → { status:"ok",
      environment:<ENVIRONMENT>,
      pipeline_modules: {
        cleaner, eda, trainer, explainer, insights, reporter, llm  # each true/false
      } }
```
Each flag is the result of attempting to import that module; used for readiness
/ smoke checks.

---

## 10. State transitions (job lifecycle)

```
        create_job
            │
            ▼
        ┌────────┐   row-limit / target / any error at any point
        │ queued │──────────────────────────────────────────────┐
        └───┬────┘                                               │
            ▼                                                    │
        cleaning ──► analyzing ──► modeling ──► explaining ──►    │
        generating_insights ──► generating_report ──► complete   │
            │                                                    ▼
            └─────────────────────────────────────────────►  failed
                                                           (error set,
                                                            completed_at set)
```
`progress` is derived from `status` via `PROGRESS_BY_STATUS`
(0/10/30/50/65/80/90/100). `complete` and `failed` both set `completed_at`.
