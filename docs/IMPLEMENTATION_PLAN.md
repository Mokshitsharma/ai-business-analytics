# Implementation Plan — AI Business Analytics System

**Status:** Draft · **Last updated:** 2026-08-28
**Companion docs:** [PRD](./PRD.md) · [TRD](./TRD.md) · [Architecture](./ARCHITECTURE.md) ·
[App Flow](./APPFLOW.md) · [Backend Schema](./BACKEND_SCHEMA.md) ·
[Roadmap](./ROADMAP.md) (product / hosting / launch / UI view)

---

## 0. Where we are today

**Committed (`aba392c`):** working CLI + Streamlit app; full 7-stage `core/`
pipeline; Gemini summary with deterministic fallback; HTML (Jinja2) + PDF
(ReportLab) reports.

**Uncommitted (`api/`):** FastAPI routers (`upload`, `jobs`, `report`,
`health`), services (`file_handler`, `job_runner`, `plan_guard`), in-memory
`JobStore`, unused `SimpleCache`. **No `api/main.py`, no router wiring, deps not
declared, zero tests.**

**Goal:** evolve from "runs on my machine" to a hosted, durable, plan-metered
multi-tenant service — without regressing the CLI/Streamlit paths.

---

## 1. Guiding principles

1. Ship the API as a working local service **before** adding infrastructure.
2. One pipeline engine — delete the duplicate orchestrator.
3. Every phase ends green: tests pass, `/health` OK, a real dataset produces a
   report.
4. Persistence and scale come after correctness and coverage.
5. No secret or plan value is ever trusted from the client.

---

## 2. Phased roadmap

| Phase | Theme | Outcome | Depends on |
|---|---|---|---|
| 0 | Housekeeping & fixes | Known bugs fixed, deps declared, tests exist | — |
| 1 | Assemble the API | `uvicorn api.main:app` serves the full async flow locally | 0 |
| 2 | Unify the pipeline | Single engine with progress callback; `job_runner` is a thin adapter | 1 |
| 3 | Persistence | Postgres + object store; API workers stateless | 2 |
| 4 | Real async + scale | Queue + worker pool; Redis; horizontal API | 3 |
| 5 | Identity, plans, metering | Users, API keys, `analyses_per_month` enforced | 3 |
| 6 | Hardening & launch | Auth on all routes, rate limits, retention, observability, CI/CD | 4, 5 |
| 7 | Product depth (optional) | Fill empty modules: model selection, richer insights, recommender | 6 |

---

## 3. Phase 0 — Housekeeping & fixes

**Exit criteria:** `pytest` runs and passes; `pip install -r requirements.txt`
gives a working API + pipeline environment; the P0/P1 bugs in TRD §8 are closed.

### Tasks
- [ ] **Declare dependencies.** Add `fastapi`, `uvicorn[standard]`,
  `python-multipart`, `PyJWT` to `requirements.txt`; pin all versions; add
  `requirements-dev.txt` (`pytest`, `pytest-cov`, `httpx`, `ruff`).
- [ ] **Fix `LLMClient` eager init** (`llm/summarizer.py`): lazy-create the
  client inside `summarize`, or catch construction in the same `try/except` as
  the call. Add a test: missing `GOOGLE_API_KEY` ⇒ fallback summary, no raise.
- [ ] **Fix deprecated pandas call** (`core/preprocessing/cleaner.py`):
  `fillna(method="ffill")` → `.ffill()`.
- [ ] **Guard PDF generator** (`reporting/pdf_generator.py`): tolerate
  `executive_summary is None` / missing `metrics`/`insights` keys.
- [ ] **Stratify the split** for classification in `core/models/trainer.py`
  (`train_test_split(..., stratify=y)` when `task_type == "classification"` and
  every class has ≥ 2 rows; fall back otherwise).
- [ ] **Datetime feature handling** (`core/features/engineer.py`): drop datetime
  columns or expand to `year/month/day/dow` numerics instead of one-hot.
- [ ] **Seed the test suite** (`tests/`):
  - `test_preprocessing.py` — dedupe, each imputation branch, type heuristic.
  - `test_models.py` — task detection (object, ≤10 unique, continuous),
    safe-CV `None` on tiny data, metric keys per task.
  - `test_pipeline.py` — end-to-end on a tiny fixture CSV (classification and
    regression), asserts report dict shape + JSON-serialisability.
  - Fixtures: 2–3 small CSVs under `tests/fixtures/`.
- [ ] **Config validation** (`configs/settings.py`): parse/validate env once;
  decide `MAX_UPLOAD_SIZE_MB` — either use it as a hard ceiling above plan
  limits or delete it.
- [ ] Add `ruff`/`black` config and a `Makefile` / `tasks.py`
  (`make test`, `make lint`, `make api`).

---

## 4. Phase 1 — Assemble the API (local, in-memory)

**Exit criteria:** `uvicorn api.main:app --reload` boots; the full Flow C→D→E
(App Flow §4–6) works end-to-end against a local file; contract tests green.

### Tasks
- [ ] **Create `api/main.py`:** instantiate `FastAPI(title=…, version="1")`,
  `include_router` for `health`, `upload`, `jobs`, `report` under an `/v1`
  prefix (keep `/health` unprefixed too for probes), add CORS, add a global
  exception handler that normalises `HTTPException.detail` to
  `{error, code, ...}` (TRD §5.2).
- [ ] **Stop trusting the `plan` form field** (`api/routers/upload.py`):
  replace `plan: str = Form("free")` with `plan = get_plan(request)`. Thread
  `plan` through `create_job` / `run_analysis_job` unchanged.
- [ ] **Add auth dependency** (even if permissive in dev): a
  `get_current_plan` FastAPI dependency wrapping `plan_guard.get_plan`; apply
  to `upload`, `jobs`, `report`.
- [ ] **Ownership stub:** store `user_id=None` on jobs now; add a
  `require_job_access(job_id, principal)` helper used by every `/jobs/*` route
  (no-op in dev, enforced in Phase 5).
- [ ] **Wire `SimpleCache`** or delete it. Recommended: use it to memoise
  `/jobs/{id}/result` plan-stripping output keyed by `(job_id, plan)`.
- [ ] **Bound the thread usage:** replace ad-hoc `threading.Thread` per upload
  with a `concurrent.futures.ThreadPoolExecutor(max_workers=N)` module
  singleton; `/upload` submits to it. (Interim until Phase 4 queue.)
- [ ] **Startup/shutdown hooks:** ensure `data/uploads` & `data/outputs` exist;
  on shutdown, mark in-flight jobs `failed("server restarted")`.
- [ ] **Contract tests** (`tests/api/`): `httpx`/`TestClient` —
  upload→poll→result→html→pdf happy path; 400s (bad type, too big, empty);
  404 unknown job; 409 report-not-ready; 403 PDF on free plan; free-plan
  result strips SHAP + summary.
- [ ] **Docs:** README section "Run the API", example `curl` sequence.
- [ ] **Commit** the `api/` package (currently untracked) with the above.

---

## 5. Phase 2 — Unify the pipeline

**Exit criteria:** exactly one implementation of the 7 stages. CLI, Streamlit,
and API all call it. Deleting `run_analysis_job`'s stage code changes no
behaviour.

### Tasks
- [ ] Extend `core/pipeline.Pipeline.run(df, target, *, plan="pro",
  progress_cb=None)`:
  - call `progress_cb(status)` before each stage (names match
    `PROGRESS_BY_STATUS`);
  - accept `plan` and apply `check_row_limit` early;
  - keep returning the full report dict + metadata (`row_count`,
    `column_count`, `target_column`, `task_type`).
- [ ] Rewrite `api/services/job_runner.run_analysis_job` as a ~15-line adapter:
  load file → `Pipeline().run(df, target, plan=plan,
  progress_cb=lambda s: job_store.update_status(job_id, s))` → render reports →
  `set_result` / `update_status`. Keep the outer `try/except → failed`.
- [ ] Point `run.py` and `app/main.py` at the same `Pipeline.run` (they nearly
  do already); Streamlit gains an optional progress bar via `progress_cb`.
- [ ] Move report rendering (HTML/PDF paths) into a small
  `reporting/render.py:render_all(report, out_dir) -> {html_path, pdf_path}`
  used by both CLI and API.
- [ ] Delete now-dead duplicate imports in `job_runner.py`.
- [ ] Update/expand `test_pipeline.py` to assert `progress_cb` is called with
  the full status sequence in order.

---

## 6. Phase 3 — Persistence

**Exit criteria:** killing and restarting the API loses **no** job state;
results survive; API process holds no job data in memory. Schema =
[Backend Schema](./BACKEND_SCHEMA.md) Part 2.

### Tasks
- [ ] Add SQLAlchemy 2.x (or `psycopg` + SQL) + Alembic. `configs/settings.py`
  gains `DATABASE_URL`.
- [ ] Create migrations for `plans`, `users` (minimal: id, email, plan_id),
  `analyses`, `reports`, `report_files`, `usage_events`. Seed `plans` from
  `PLAN_LIMITS`.
- [ ] Introduce a `JobRepository` interface; provide `InMemoryJobRepository`
  (existing behaviour, for tests) and `SqlJobRepository`. Swap `job_store`
  singleton for an injected repository.
- [ ] `plan_guard`: load limits from the `plans` table (cache in memory /
  Redis later); keep the dict as a fallback/seed.
- [ ] Object store: add `storage.py` with a `Storage` interface —
  `LocalStorage` (current `data/…` behaviour) and `S3Storage`. `save_upload`
  and report rendering write via `Storage`; DB stores object keys.
- [ ] `FileResponse` endpoints become redirects to presigned URLs (S3) or
  stream from `LocalStorage` in dev.
- [ ] Migrate `run_analysis_job` to: create `analyses` row → update
  `status/progress` columns → write `reports` + `report_files` rows.
- [ ] Backfill/no-op: no existing prod data, so no data migration needed.
- [ ] Tests: repository contract tests run against both implementations;
  restart test (spin API, submit job, restart, assert job still queryable).

---

## 7. Phase 4 — Real async & scale

**Exit criteria:** pipeline execution runs in a separate worker process;
multiple API replicas can run behind a load balancer; a crashed worker retries
the job.

### Tasks
- [ ] Choose a task runner: **Celery** or **RQ** or **Arq** (async). Broker =
  Redis (Backend Schema §2.10).
- [ ] `/upload` enqueues `run_analysis(analysis_id)` instead of spawning a
  thread; returns `202` immediately.
- [ ] Worker entrypoint (`worker.py`): consumes the queue, runs
  `Pipeline.run` with a `progress_cb` that writes to Postgres **and** Redis
  (`job:progress:<id>`).
- [ ] `/jobs/{id}/status` reads progress from Redis first, Postgres fallback.
- [ ] Idempotency + locking: `lock:analysis:<id>`; `retry_count` column;
  max retries → `failed`.
- [ ] Concurrency controls: worker pool size, per-job memory ceiling, timeout
  (kill + `failed("timeout")`).
- [ ] Containerise: `Dockerfile` (api), same image runs `worker.py`;
  `docker-compose.yml` for local (api + worker + postgres + redis + minio).
- [ ] Load test: N concurrent uploads, assert throughput and no lost jobs.

---

## 8. Phase 5 — Identity, plans & metering

**Exit criteria:** a real user can sign up, gets a plan, receives an API key,
and `analyses_per_month` is enforced with a clear upgrade path.

### Tasks
- [ ] Auth: email/password (Argon2/bcrypt) + session JWT issuance
  (`/v1/auth/*`), plus `api_keys` table + `Authorization: Bearer <api_key>`
  path. `get_plan` resolves `user → users.plan_id`.
- [ ] Apply `get_current_user` dependency to all `/v1` routes; enforce
  `require_job_access` (job.user_id == principal).
- [ ] Metering: write `usage_events` on submit/complete/fail/pdf-download.
- [ ] Quota gate in `/upload`: count `analysis_submitted` in the current
  `billing_period` vs `plans.analyses_per_month` (`-1` = skip); `429`/`403`
  with `upgrade_to` when exceeded.
- [ ] Monthly window: `users.plan_renews_at` drives `billing_period`; a daily
  job rolls it forward.
- [ ] Billing hook (optional): Stripe webhook → `users.plan_id` +
  `plan_renews_at`.
- [ ] Admin: minimal endpoint/script to set a user's plan.
- [ ] Tests: quota exhaustion, plan upgrade unlocks SHAP/PDF/summary,
  cross-user job access denied.

---

## 9. Phase 6 — Hardening & launch

**Exit criteria:** deployable via CI/CD, observable, rate-limited, data
retention enforced, security review passed.

### Tasks
- [ ] **Rate limiting** (Redis token bucket) per user/API key and per IP on
  `/upload`.
- [ ] **Retention reaper**: cron deletes uploads > 30 d, reports past
  `expires_at`; cascade object-store cleanup.
- [ ] **Observability**: structured JSON logs with request/correlation IDs;
  Prometheus metrics (`/metrics`): job counts by status, stage durations,
  LLM-fallback rate, queue depth; error tracking (Sentry).
- [ ] **Security**: authenticated read endpoints, CORS allowlist, upload
  content sniffing (not just extension), size cap enforced pre-buffering,
  dependency scan, secrets from a manager (not `.env`) in prod. Run the
  repo's `security-review`.
- [ ] **Resilience**: LLM call timeout + retry/backoff; SHAP time budget;
  pipeline hard timeout; graceful worker shutdown drains in-flight jobs.
- [ ] **CI/CD**: GitHub Actions — lint, test+coverage gate, build image, run
  migrations, deploy api + worker; smoke test `/health` post-deploy.
- [ ] **Docs**: OpenAPI published, API guide, runbook (restart, backfill,
  reaper, scale workers), architecture diagram export.
- [ ] **Perf**: cache identical-dataset results (hash of file + target) via
  Redis `cache:result:*`.

---

## 10. Phase 7 — Product depth (optional, post-launch)

Fill the empty modules already scaffolded in the repo:

| Module | Build |
|---|---|
| `core/models/selector.py`, `registry.py` | try LogisticRegression/LinearRegression + RandomForest, pick best by CV; model registry for reproducibility |
| `core/models/evaluator.py` | already implemented — wire into pipeline for a standalone eval block (confusion matrix, ROC-AUC, residuals) |
| `core/preprocessing/validator.py` | pre-flight dataset validation (leakage checks, constant columns, ID-like columns, target quality) surfaced to the user |
| `core/preprocessing/transformer.py`, `core/features/encoder.py` | pluggable transforms, target encoding, datetime expansion, outlier capping |
| `core/eda/stats.py`, `visualizer.py` | hypothesis tests; embed base64 charts (matplotlib) into the HTML report |
| `core/insights/{trends,anomaly,segmentation}.py` | move rule logic out of the monolithic `generator.py`; add seasonality, changepoints, clustering-based segments |
| `core/xai/importance.py` | permutation importance as a SHAP cross-check |
| `llm/recommender.py` | dedicated recommendations prompt/section separate from the summary |
| `app/pages/*`, `app/components/*` | multi-page Streamlit: Upload / Dashboard / Insights / Reports, reusable chart+table components |
| `configs/model_config.yaml` | externalise model families, hyperparameters, CV settings, sample sizes |

---

## 11. Cross-phase definition of done

- [ ] `make lint && make test` green; coverage ≥ 70% on `core/` and `api/`.
- [ ] `GET /health` returns all pipeline modules `true`.
- [ ] A classification dataset and a regression dataset each produce a valid
  HTML + PDF report.
- [ ] LLM disabled (`GOOGLE_API_KEY=""`) still produces a report (fallback).
- [ ] No secret or plan value read from a client-controlled field.
- [ ] CHANGELOG / commit trail per phase; docs in `docs/` updated in the same PR.

---

## 12. Suggested sequencing & rough effort

| Phase | Rough size | Can parallelise with |
|---|---|---|
| 0 | S | — |
| 1 | M | — |
| 2 | S–M | 1 (tail) |
| 3 | L | — |
| 4 | L | 5 |
| 5 | M–L | 4 |
| 6 | M | — |
| 7 | ongoing | anything, post-launch |

Critical path to a hostable MVP: **0 → 1 → 2 → 3 → 5 → 6**
(Phase 4 can be deferred if a bounded `ThreadPoolExecutor` + single API replica
is acceptable at launch scale).
