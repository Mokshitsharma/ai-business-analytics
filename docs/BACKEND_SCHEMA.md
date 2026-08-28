# Backend Schema — AI Business Analytics System

**Status:** Draft · **Last updated:** 2026-08-28
**Companion docs:** [PRD](./PRD.md) · [TRD](./TRD.md) · [Architecture](./ARCHITECTURE.md) ·
[App Flow](./APPFLOW.md) · [Implementation Plan](./IMPLEMENTATION_PLAN.md)

This document has two parts:
- **Part 1 — Current state:** the in-memory / on-disk structures the code uses today.
- **Part 2 — Target state:** the proposed persistent schema (PostgreSQL + Redis +
  object store) required to host the service.

---

# Part 1 — Current state (no database)

## 1.1 Job record — `api/job_store.JobStore._jobs[job_id]`

In-process dict, guarded by `threading.Lock`, lost on restart.

| Field | Type | Set by | Notes |
|---|---|---|---|
| `job_id` | `str` (UUID4) | `create_job` | primary key |
| `filename` | `str` | `create_job` | original upload name |
| `target_column` | `str` | `create_job` | may be `""` (⇒ last column at run time) |
| `plan` | `str` | `create_job` | `"free" \| "starter" \| "pro"` |
| `status` | `str` | `update_status` | see state machine below |
| `progress` | `int` | derived | `PROGRESS_BY_STATUS[status]` |
| `error` | `str \| None` | `update_status("failed", …)` | normalised message |
| `result` | `dict \| None` | `set_result` | full report + metadata (§1.2) |
| `created_at` | `float` | `create_job` | `time.time()` epoch seconds |
| `completed_at` | `float \| None` | `update_status` | set on `complete` or `failed` |

**Status enum / progress map (`PROGRESS_BY_STATUS`):**

| status | progress |
|---|---|
| `queued` | 0 |
| `cleaning` | 10 |
| `analyzing` | 30 |
| `modeling` | 50 |
| `explaining` | 65 |
| `generating_insights` | 80 |
| `generating_report` | 90 |
| `complete` | 100 |
| `failed` | *(unchanged; `error` + `completed_at` set)* |

## 1.2 Job `result` dict (built in `api/services/job_runner.py`)

```
{
  # from reporting/report_builder.ReportBuilder.build()
  "executive_summary": str | None,        # None if plan-locked at /result
  "executive_summary_locked": bool,        # added only when locked
  "metrics": {                             # from ModelTrainer
     "accuracy"?: float, "f1_score"?: float,        # classification
     "rmse"?: float, "r2_score"?: float,            # regression
     "cv_score": float | None,
     "task_type": "classification" | "regression"
  },
  "insights": {                            # from InsightGenerator
     "trends": [str], "anomalies": [str], "segments": [str],
     "predictions": {"mean_prediction": float, "min_prediction": float, "max_prediction": float}
  },
  "eda": {                                 # from EDAAnalyzer
     "summary_stats": {...}, "correlations": {"correlation_matrix": {...}, "high_correlations": {...}},
     "distributions": {...}, "trends": {...}, "data_quality": {...}
  },
  "explanations":                          # from ShapExplainer, OR
     {"global_importance": {feature: float}, "local_explanations": [ {...} ]}
     | {"error": str}
     | {"locked": true, "message": str},   # plan-locked at /result

  # added by job_runner
  "report_html_path": str,                 # data/outputs/<job_id>/report.html
  "report_pdf_path":  str,                 # data/outputs/<job_id>/report.pdf
  "row_count": int,
  "column_count": int,
  "target_column": str,
  "task_type": "classification" | "regression"
}
```

## 1.3 Cache entry — `api/cache.SimpleCache._store[key]`

| Element | Type | Notes |
|---|---|---|
| key | `str` | caller-defined |
| value | `(data: Any, expires_at: float \| None)` | `expires_at = time.time() + ttl` or `None` for no expiry |

Thread-safe; lazy expiry on `get`. **Not currently referenced by any router.**

## 1.4 Plan limits — `api/services/plan_guard.PLAN_LIMITS` (static config, not data)

| key | free | starter | pro |
|---|---|---|---|
| `max_file_size_mb` | 5 | 50 | 500 |
| `max_rows` | 1000 | 50000 | 500000 |
| `analyses_per_month` | 1 | 10 | -1 (unlimited) |
| `pdf_report` | false | true | true |
| `shap_access` | false | true | true |
| `ai_summary` | false | true | true |

## 1.5 On-disk layout

| Path | Contents | Written by |
|---|---|---|
| `data/uploads/<job_id>/<filename>` | raw uploaded dataset | `file_handler.save_upload` |
| `data/outputs/<job_id>/report.html` | rendered HTML report | `HTMLReportGenerator` |
| `data/outputs/<job_id>/report.pdf` | rendered PDF report | `PDFReportGenerator` |
| `data/outputs/report.{html,pdf}` | CLI / Streamlit reports (no job id) | same generators (default path) |

No retention, quota, or cleanup logic exists.

## 1.6 Auth token (consumed, not stored)

JWT, HS256, secret = `JWT_SECRET`. Only claim read: `plan`
(`"free" | "starter" | "pro"`). No issuer, audience, or expiry checks in code.
There is **no user record** anywhere today.

---

# Part 2 — Target persistent schema (PostgreSQL)

Rationale: durability across restarts/deploys, horizontal scaling of stateless
API workers, real usage metering, and account/billing. See
[Architecture](./ARCHITECTURE.md) §6.2.

## 2.1 Entity-relationship overview

```
users ──1:N── api_keys
  │
  1:N
  │
analyses ──1:1── reports
  │                 │
  │                 1:N
  │              report_files   (html / pdf object-store keys)
  1:N
usage_events        plans (reference table)
```

## 2.2 `plans` (reference / seed data)

| column | type | notes |
|---|---|---|
| `id` | `text` PK | `free`, `starter`, `pro` |
| `display_name` | `text` | "Free", "Starter", "Pro" |
| `max_file_size_mb` | `integer` | |
| `max_rows` | `integer` | |
| `analyses_per_month` | `integer` | `-1` = unlimited |
| `pdf_report` | `boolean` | |
| `shap_access` | `boolean` | |
| `ai_summary` | `boolean` | |
| `price_cents_month` | `integer` | billing (nullable) |
| `created_at` / `updated_at` | `timestamptz` | |

Seed rows mirror `PLAN_LIMITS` exactly so `plan_guard` can load from DB instead
of a hard-coded dict.

## 2.3 `users`

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()` |
| `email` | `citext` UNIQUE NOT NULL | |
| `password_hash` | `text` | nullable if SSO-only |
| `plan_id` | `text` FK → `plans.id` NOT NULL | default `'free'` |
| `plan_renews_at` | `timestamptz` | for monthly quota window |
| `status` | `text` | `active \| suspended \| deleted` |
| `created_at` / `updated_at` | `timestamptz` | |

Indexes: `UNIQUE(email)`, `INDEX(plan_id)`.

## 2.4 `api_keys` (programmatic access; replaces raw JWT-only model)

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | |
| `user_id` | `uuid` FK → `users.id` NOT NULL | |
| `name` | `text` | user label |
| `key_hash` | `text` NOT NULL | store hash only (e.g. SHA-256) |
| `key_prefix` | `text` | first 8 chars, for display/lookup |
| `last_used_at` | `timestamptz` | |
| `revoked_at` | `timestamptz` | soft revoke |
| `created_at` | `timestamptz` | |

Indexes: `INDEX(user_id)`, `UNIQUE(key_hash)`, `INDEX(key_prefix)`.
JWTs remain valid for browser sessions; the `plan` is now resolved from
`users.plan_id`, not a token claim.

## 2.5 `analyses` (replaces the in-memory job record)

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | == public `job_id` |
| `user_id` | `uuid` FK → `users.id` | nullable for anonymous/dev |
| `plan_id` | `text` FK → `plans.id` NOT NULL | snapshot of plan at submit time |
| `status` | `text` NOT NULL | enum, §2.9 |
| `progress` | `smallint` NOT NULL DEFAULT 0 | 0–100 |
| `original_filename` | `text` NOT NULL | |
| `file_extension` | `text` NOT NULL | `.csv` etc. |
| `file_size_bytes` | `bigint` NOT NULL | |
| `upload_object_key` | `text` NOT NULL | object-store key of raw file |
| `target_column` | `text` | null ⇒ resolved to last column |
| `resolved_target_column` | `text` | actual column used |
| `task_type` | `text` | `classification \| regression` |
| `row_count` | `integer` | post-clean |
| `column_count` | `integer` | post-clean |
| `error_code` | `text` | machine code, null on success |
| `error_message` | `text` | human message |
| `queued_at` | `timestamptz` NOT NULL DEFAULT now() | |
| `started_at` | `timestamptz` | worker pick-up |
| `completed_at` | `timestamptz` | terminal (`complete`/`failed`) |
| `worker_id` | `text` | which worker ran it |
| `retry_count` | `smallint` NOT NULL DEFAULT 0 | |

Indexes: `INDEX(user_id, queued_at DESC)`, `INDEX(status)`,
`INDEX(status, queued_at)` (queue scan), partial `INDEX(user_id) WHERE status
NOT IN ('complete','failed')`.

## 2.6 `reports` (structured pipeline output — 1:1 with `analyses`)

| column | type | notes |
|---|---|---|
| `analysis_id` | `uuid` PK, FK → `analyses.id` ON DELETE CASCADE | |
| `executive_summary` | `text` | null if LLM-locked/failed and no fallback stored |
| `summary_source` | `text` | `llm \| fallback \| locked` |
| `metrics` | `jsonb` NOT NULL | `{accuracy?, f1_score?, rmse?, r2_score?, cv_score, task_type}` |
| `insights` | `jsonb` NOT NULL | `{trends[], anomalies[], segments[], predictions{}}` |
| `eda` | `jsonb` NOT NULL | full EDA dict (§1.2) |
| `explanations` | `jsonb` NOT NULL | `{global_importance{}, local_explanations[]}` or `{error}` |
| `created_at` | `timestamptz` NOT NULL | |

`jsonb` GIN index only if querying inside (not expected initially).
Large EDA blobs: consider a size guard / truncation policy.

## 2.7 `report_files` (rendered artefacts)

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | |
| `analysis_id` | `uuid` FK → `analyses.id` ON DELETE CASCADE | |
| `kind` | `text` NOT NULL | `html \| pdf` |
| `object_key` | `text` NOT NULL | object-store key |
| `content_type` | `text` NOT NULL | `text/html \| application/pdf` |
| `size_bytes` | `bigint` | |
| `created_at` | `timestamptz` NOT NULL | |
| `expires_at` | `timestamptz` | retention TTL |

Index: `UNIQUE(analysis_id, kind)`.

## 2.8 `usage_events` (metering — enables `analyses_per_month`)

| column | type | notes |
|---|---|---|
| `id` | `uuid` PK | |
| `user_id` | `uuid` FK → `users.id` NOT NULL | |
| `analysis_id` | `uuid` FK → `analyses.id` | nullable (e.g. rejected pre-job) |
| `event_type` | `text` NOT NULL | `analysis_submitted \| analysis_completed \| analysis_failed \| pdf_downloaded` |
| `plan_id` | `text` NOT NULL | plan at event time |
| `billing_period` | `date` NOT NULL | first day of the user's plan month |
| `created_at` | `timestamptz` NOT NULL DEFAULT now() | |

Index: `INDEX(user_id, billing_period, event_type)`.
Quota check = `COUNT(*) WHERE event_type='analysis_submitted' AND
billing_period = current period` vs `plans.analyses_per_month`.

## 2.9 Enumerations

```
analysis_status:
  queued | cleaning | analyzing | modeling | explaining
  | generating_insights | generating_report | complete | failed

task_type:        classification | regression
report_file_kind: html | pdf
summary_source:   llm | fallback | locked
user_status:      active | suspended | deleted
```

Implement as Postgres `ENUM` types or `text` + `CHECK` constraints (latter is
easier to evolve).

## 2.10 Redis (ephemeral, not source of truth)

| Key pattern | Type | TTL | Purpose |
|---|---|---|---|
| `job:progress:<analysis_id>` | string/hash | 1 h | fast progress reads without hitting Postgres |
| `ratelimit:<user_id>:<window>` | counter | window | API rate limiting |
| `cache:result:<hash>` | string (JSON) | configurable | `SimpleCache` replacement |
| `queue:analyses` | list / stream | — | broker for the worker pool (or use Celery/RQ native) |
| `lock:analysis:<id>` | string | short | prevent double processing |

## 2.11 Object store (S3-compatible)

| Prefix | Contents | Lifecycle |
|---|---|---|
| `uploads/<analysis_id>/<filename>` | raw dataset | delete after N days |
| `reports/<analysis_id>/report.html` | rendered HTML | delete at `report_files.expires_at` |
| `reports/<analysis_id>/report.pdf` | rendered PDF | same |

## 2.12 Migration mapping (in-memory → tables)

| Today | Target |
|---|---|
| `JobStore._jobs[job_id]` | `analyses` row (+ `reports`, `report_files`) |
| `job["result"]` sub-keys | split across `reports` / `analyses` metadata |
| `data/uploads/<job_id>/…` | `uploads/<analysis_id>/…` object key |
| `data/outputs/<job_id>/…` | `reports/<analysis_id>/…` object key |
| `PLAN_LIMITS` dict | `plans` table (seeded identically) |
| JWT `plan` claim | `users.plan_id` (JWT now only identifies the user) |
| *(none)* | `users`, `api_keys`, `usage_events` |
| `SimpleCache` | Redis `cache:*` |

## 2.13 Retention & privacy (to define)

- Default raw-upload retention: **30 days** (configurable), then hard delete.
- Rendered reports: **90 days** or until user deletes the analysis.
- `DELETE FROM analyses` cascades to `reports`, `report_files`; object-store
  keys removed by a reaper job.
- Encrypt object-store buckets at rest; consider column-level encryption for
  `reports.eda`/`insights` if datasets are sensitive.
- GDPR/erasure: deleting a `users` row must cascade or anonymise all
  `analyses` / `usage_events`.
