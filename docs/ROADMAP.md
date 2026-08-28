# Roadmap — Future Changes & Plans

**Status:** Living document · **Last updated:** 2026-08-28
**Related:** [Implementation Plan](./IMPLEMENTATION_PLAN.md) (engineering phases in detail) ·
[PRD](./PRD.md) · [Architecture](./ARCHITECTURE.md)

This document is the product / go-to-market / design view of where the project
is going. The granular engineering breakdown lives in
[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md); this one covers **hosting**,
**launch**, **UI design**, and the **feature roadmap** at a level a
non-engineer can follow.

---

## 1. Vision

Anyone with a spreadsheet should be able to get a data-scientist-quality
analysis of it in under a minute — cleaning, a trained model, honest accuracy
numbers, an explanation of what drives the outcome, and a plain-language
executive summary they can forward to their boss. No notebooks, no ML
knowledge, no setup.

The long-term product is a hosted service with a free tier, paid plans for
larger data and richer output, and an API for developers who want to embed
automated analysis in their own products.

---

## 2. Where we are today (2026-08-28)

| Capability | State |
|---|---|
| Core ML pipeline (clean → EDA → train → SHAP → insights → report) | ✅ working |
| CLI (`run.py`) | ✅ working |
| FastAPI backend + async jobs (`api/`) | ✅ working locally |
| Browser UI (upload → progress → report) | ✅ working locally |
| HTML + PDF report generation | ✅ working |
| AI executive summary (Gemini) with safe fallback | ✅ working (needs a valid key) |
| Plan tiers (free / starter / pro) defined & partly enforced | 🟡 partial (no metering) |
| Persistence (DB, object storage) | ❌ in-memory only |
| Hosting / deployment | ❌ not started |
| Auth / user accounts / billing | ❌ not started |

**Blocking gap for a real launch:** everything is in-memory and single-process.
A restart loses all jobs. See §3.

---

## 3. Hosting & infrastructure plan

### 3.1 Target architecture (hosted)

```
              Users ──HTTPS──►  CDN / Load balancer
                                      │
                          ┌───────────┴───────────┐
                          ▼                       ▼
                   API service (N replicas, stateless)
                          │        │        │
                          ▼        ▼        ▼
                    Postgres    Redis    Object storage (S3-compatible)
                   (jobs,      (cache,   (uploads + rendered reports)
                    users,      queue,
                    usage)      rate limits)
                          ▲
                   Worker service (M replicas)
                   runs the analysis pipeline off a queue
```

### 3.2 Hosting options (decision pending)

| Option | Fit | Notes |
|---|---|---|
| **Render / Railway / Fly.io** (PaaS) | ✅ recommended for v1 | Managed Postgres + Redis add-ons, container deploys, cheap, fast to stand up. Fly.io if we want regions close to users. |
| **AWS (ECS/Fargate + RDS + ElastiCache + S3)** | Later, at scale | More control and cheaper at volume; more ops overhead. Migrate here if usage/cost justifies it. |
| **Single VPS + Docker Compose** | Only for a private demo | No HA, manual scaling. Fine to show investors, not for paying users. |

**Plan:** launch on a PaaS (Render or Railway). Containerise the API and the
worker from one image. Use the provider's managed Postgres and Redis.
Object storage: the provider's S3-compatible bucket, or Cloudflare R2 / AWS S3.

### 3.3 Infrastructure work required (maps to Implementation Plan Phases 3–4 & 6)

- [ ] Postgres schema + migrations (`docs/BACKEND_SCHEMA.md` Part 2)
- [ ] Move `JobStore` → Postgres, `SimpleCache` → Redis, disk paths → object storage
- [ ] Real task queue (Celery / RQ / Arq) + separate worker process
- [ ] `Dockerfile` + `docker-compose.yml` (local parity) + deploy config
- [ ] Secrets from the platform's secret manager, not `.env`
- [ ] CI/CD: GitHub Actions → lint, test, build image, run migrations, deploy, smoke-test `/health`
- [ ] Backups (daily Postgres snapshot), log aggregation, error tracking (Sentry), uptime monitor
- [ ] Data retention job: purge uploads after 30 days, reports after 90
- [ ] Rate limiting + basic WAF / abuse protection on `/upload`

### 3.4 Rough monthly cost at small scale (estimate)

| Item | Est. / month |
|---|---|
| PaaS API + worker (2 small instances) | $15–40 |
| Managed Postgres (small) | $10–20 |
| Managed Redis (small) | $10–15 |
| Object storage + egress (light) | $1–5 |
| Domain + email | $2–5 |
| **Total** | **~$40–85** before meaningful traffic |

LLM (Gemini) cost is usage-based and passed through plan limits.

---

## 4. Launch plan

### Stage 0 — Private alpha (now → +2 weeks)
- Deploy to a PaaS behind a login wall or a shared password.
- Invite 5–10 friendly users with real datasets.
- Goal: confirm the pipeline handles messy real-world data; collect failure cases.

### Stage 1 — Private beta (+2 → +6 weeks)
- Real accounts (email + password), free tier only.
- Persistence live (no more lost jobs), usage metering on.
- Onboarding: 3 sample datasets one click away.
- Feedback widget in-app; weekly triage.
- Goal: 50–100 signups, >90% job success rate, <60s median time-to-report.

### Stage 2 — Public launch (+6 → +10 weeks)
- Paid plans switched on (Stripe): Starter and Pro (see PRD §5.4).
- Landing page with real copy, sample report, pricing.
- Launch channels: LinkedIn, relevant subreddits / communities, Show HN,
  Product Hunt, a short demo video.
- API docs published (`/docs` OpenAPI + a guide).
- Goal: first paying customers; watch free→paid conversion on "limit exceeded".

### Stage 3 — Post-launch iteration (ongoing)
- Prioritise from beta feedback and support volume.
- See §6 feature roadmap.

### Launch checklist
- [ ] Custom domain + HTTPS
- [ ] Privacy policy + terms (we store users' business data — say how, and for how long)
- [ ] Data deletion / account deletion flow
- [ ] Status page
- [ ] Support inbox
- [ ] Pricing page + Stripe checkout + webhook → plan update
- [ ] Abuse / rate limits verified
- [ ] Backups + restore tested once

---

## 5. UI / UX design roadmap

The visual direction is set — "warm editorial": calm paper background, one teal
accent, serif display headings, monospaced numerals. It's captured as a design
canvas (`design/*.dc.html`) and implemented in `api/static/index.html` for the
three core screens.

### Near term
- [ ] **Report polish** — real chart for SHAP importance (horizontal bars →
  proper d3/Chart), collapsible EDA sections, sticky in-page nav for long reports.
- [ ] **Better fallback summary presentation** — render the structured recap as
  formatted sections, not a text blob.
- [ ] **Empty / error states** — friendly copy for: no columns detected, all-null
  target, row-limit exceeded (with an upgrade CTA), job failed.
- [ ] **Mobile pass** — the report is dense; verify and fix at 390px.
- [ ] **Loading skeletons** on the report screen while `/result` loads.

### Mid term
- [ ] **History screen** — list past analyses, re-open a report, re-run with a
  new target. (Needs persistence.)
- [ ] **Dashboard / home** — recent analyses, usage vs plan limits, quick re-run.
- [ ] **Dark mode** — the alternate "dense dark dashboard" direction from the
  canvas becomes an actual theme toggle.
- [ ] **Multi-page app** — fill out `app/pages/*` equivalents: Upload / History /
  Report / Settings, shared chart + table components.
- [ ] **Plan-locked UI** — show locked SHAP / AI-summary / PDF sections with a
  clear "upgrade to unlock" treatment instead of hiding them.

### Longer term
- [ ] **Interactive report** — filter insights, drill into a segment, hover SHAP
  values per row.
- [ ] **Shareable report links** — a read-only public URL for a single report.
- [ ] **In-app dataset preview & column typing** — let the user correct a
  misdetected column type before running.
- [ ] **Design system** — extract tokens + components (currently inline in one
  HTML file) into a small reusable set; consider a framework (React/Svelte) once
  the app has 4+ screens.

---

## 6. Product / feature roadmap

### Modelling
- [ ] Try multiple model families (LogisticRegression / LinearRegression /
  GradientBoosting) and pick the best by cross-validation, not just RandomForest.
- [ ] Class-imbalance handling (class weights / resampling) + calibration.
- [ ] Leakage / data-quality pre-flight: warn on ID-like columns, constant
  columns, target leakage, tiny classes — before running.
- [ ] Confusion matrix, ROC/PR curves, residual plots in the report.
- [ ] Permutation importance as a cross-check on SHAP.
- [ ] Time-series awareness: detect a date column, offer a chronological
  train/test split and simple forecasting.

### Insights & reporting
- [ ] Move rule-based insight logic out of one monolithic file; add seasonality,
  changepoints, and clustering-based segments.
- [ ] Dedicated recommendations section (separate LLM prompt from the summary).
- [ ] Report templates / branding options (logo, colours) for paid plans.
- [ ] Export to PowerPoint / Google Slides, and a one-page "board summary".

### Data input
- [ ] Multiple files / join two datasets.
- [ ] Direct connectors: Google Sheets, Postgres, Snowflake, S3.
- [ ] Larger files via chunked upload + sampling strategy.

### Platform
- [ ] Scheduled / recurring analyses ("re-run this every Monday").
- [ ] Webhooks / Zapier on "analysis complete".
- [ ] Team workspaces: shared history, roles, seat-based billing.
- [ ] Full public API with SDKs (Python first).
- [ ] Swap `google.generativeai` → `google.genai` (current package is
  end-of-life); make the LLM provider pluggable (Gemini / Claude / OpenAI).

---

## 7. Near-term backlog (next 2–4 weeks)

Ordered. These are the concrete next changes.

1. **Persistence** — Postgres + migrations; `JobStore` → DB; object storage for
   uploads/reports. (Unblocks everything else.)
2. **Deploy to a PaaS** — Dockerfile, managed Postgres/Redis, `/health`
   smoke-test, custom domain.
3. **Auth** — email/password signup, session JWT, `get_plan()` reads
   `users.plan_id`.
4. **Usage metering** — `usage_events`, enforce `analyses_per_month` with an
   upgrade CTA.
5. **Real task queue + worker process** — stop running analysis in a web
   thread.
6. **UI: history screen + report polish + error states.**
7. **CI/CD** — GitHub Actions: lint, test (add real tests — `tests/` is empty),
   build, deploy.
8. **LLM** — migrate off the deprecated Gemini package; make provider
   configurable.
9. **Landing page + pricing + Stripe** (for Stage 2).

---

## 8. Open questions

- Hosting provider: Render vs Railway vs Fly — decide before Phase 3.
- Managed queue vs self-run (Celery/RQ) — depends on provider.
- LLM provider for GA — Gemini (cheap) vs Claude/GPT (quality); pluggable either way.
- Do we keep the Streamlit app, or retire it once the web UI has history + auth?
- Free-tier limits — are 1 analysis/month and 1,000 rows too tight? Revisit after beta.
- Data residency / compliance — needed before enterprise customers.
