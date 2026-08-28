# api/routers/health.py

from fastapi import APIRouter

from configs.settings import ENVIRONMENT

router = APIRouter()


def _module_ok(import_fn) -> bool:
    try:
        import_fn()
        return True
    except Exception:
        return False


@router.get("/health")
def health_check():
    pipeline_modules = {
        "cleaner": _module_ok(lambda: __import__(
            "core.preprocessing.cleaner", fromlist=["DataCleaner"]
        )),
        "eda": _module_ok(lambda: __import__(
            "core.eda.analyzer", fromlist=["EDAAnalyzer"]
        )),
        "trainer": _module_ok(lambda: __import__(
            "core.models.trainer", fromlist=["ModelTrainer"]
        )),
        "explainer": _module_ok(lambda: __import__(
            "core.xai.shap_explainer", fromlist=["ShapExplainer"]
        )),
        "insights": _module_ok(lambda: __import__(
            "core.insights.generator", fromlist=["InsightGenerator"]
        )),
        "reporter": _module_ok(lambda: __import__(
            "reporting.report_builder", fromlist=["ReportBuilder"]
        )),
        "llm": _module_ok(lambda: __import__(
            "llm.client", fromlist=["LLMClient"]
        )),
    }

    return {
        "status": "ok",
        "environment": ENVIRONMENT,
        "pipeline_modules": pipeline_modules,
    }
