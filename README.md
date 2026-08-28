# AI Business Analytics System

Upload a business dataset (CSV/XLSX) and get an automated ML analysis: data
cleaning, EDA, model training, SHAP explainability, business insights, and an
AI-written executive summary — packaged into an HTML and PDF report.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

Add your Gemini API key to `.env`:

```
GOOGLE_API_KEY=your-key-here
```

(If it's missing or the LLM call fails, the executive summary falls back to a
structured plain-text summary instead of crashing.)

## Usage

### CLI

```bash
python run.py --file path/to/data.csv --target target_column_name
```

Generates `data/outputs/report.html` and `data/outputs/report.pdf`.

### Web app (FastAPI + browser UI)

```bash
uvicorn api.main:app --reload
```

Then open http://127.0.0.1:8000 — upload a file, pick the target column, watch
the staged progress, and read / download the report. The same server exposes a
JSON API:

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/health` | pipeline module health |
| `POST` | `/upload` | multipart `file` + `target_column`; returns `job_id` |
| `GET`  | `/jobs/{id}/status` | status + progress (0–100) |
| `GET`  | `/jobs/{id}/result` | full report JSON once complete |
| `GET`  | `/jobs/{id}/report/html` · `/report/pdf` | rendered report files |

Analysis runs in a background thread; poll `/jobs/{id}/status` until
`complete`. In development every caller is treated as the `pro` plan; in
production the plan is read from a `plan` claim on a bearer JWT
(`api/services/plan_guard.py`).

### Legacy Streamlit app

```bash
streamlit run app/main.py
```

### Sample data

```bash
python scripts/generate_mock_data.py
```

Writes `data/samples/customer_churn.csv` (classification),
`monthly_sales.csv` (regression) and `tiny_classification.csv` (small-data edge
cases).

## Pipeline

`core/pipeline.py` orchestrates:

1. **Clean** (`core/preprocessing/cleaner.py`) — dedupe, type detection, missing-value imputation
2. **EDA** (`core/eda/analyzer.py`) — stats, correlations, distributions, data quality
3. **Feature engineering** (`core/features/engineer.py`) — scaling + one-hot encoding
4. **Train** (`core/models/trainer.py`) — auto classification/regression via RandomForest, with safe cross-validation for small datasets
5. **Explain** (`core/xai/shap_explainer.py`) — SHAP global/local feature importance
6. **Insights** (`core/insights/generator.py`) — trend, anomaly, and segment detection
7. **Report** (`reporting/report_builder.py`) — assembles everything plus an LLM-generated executive summary (`llm/`), rendered to HTML/PDF (`reporting/`)
