# api/services/job_runner.py

from pathlib import Path

from core.preprocessing.cleaner import DataCleaner
from core.eda.analyzer import EDAAnalyzer
from core.features.engineer import FeatureEngineer
from core.models.trainer import ModelTrainer
from core.xai.shap_explainer import ShapExplainer
from core.insights.generator import InsightGenerator
from reporting.report_builder import ReportBuilder
from reporting.html_generator import HTMLReportGenerator
from reporting.pdf_generator import PDFReportGenerator

from api.job_store import job_store
from api.services.plan_guard import check_row_limit
from utils.file_handler import load_dataset
from utils.logger import get_logger
from utils.serialization import to_json_safe

logger = get_logger(__name__)


def run_analysis_job(job_id: str, file_path: str, target_column: str, plan: str) -> None:
    """
    Runs the full analysis pipeline in a background thread, updating job
    status at each stage. Never raises: all errors are caught and recorded
    as a failed job so the polling frontend always gets a clean response.
    """

    try:
        df = load_dataset(str(file_path))
        check_row_limit(df, plan)

        if not target_column:
            target_column = df.columns[-1]

        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found in dataset")

        job_store.update_status(job_id, "cleaning")
        cleaned_df = DataCleaner().clean(df)

        job_store.update_status(job_id, "analyzing")
        eda_results = EDAAnalyzer().analyze(cleaned_df)

        job_store.update_status(job_id, "modeling")
        X, y = FeatureEngineer().transform(cleaned_df, target_column)
        model_results = ModelTrainer().train(X, y)
        model = model_results["model"]
        metrics = dict(model_results["metrics"])
        metrics["task_type"] = model_results["task_type"]

        job_store.update_status(job_id, "explaining")
        try:
            shap_results = ShapExplainer().explain(model, X)
        except Exception as exc:
            logger.warning("SHAP explanation failed for job %s: %s", job_id, exc)
            shap_results = {"error": str(exc)}

        job_store.update_status(job_id, "generating_insights")
        predictions = model.predict(X)
        insights = InsightGenerator().generate(cleaned_df, predictions)

        job_store.update_status(job_id, "generating_report")
        report = ReportBuilder().build(
            eda_results=eda_results,
            metrics=metrics,
            insights=insights,
            explanations=shap_results,
        )

        output_dir = Path("data/outputs") / job_id
        html_path = HTMLReportGenerator().generate(
            report, output_path=str(output_dir / "report.html")
        )
        pdf_path = PDFReportGenerator().generate(
            report, output_path=str(output_dir / "report.pdf")
        )

        result = {
            **report,
            "report_html_path": html_path,
            "report_pdf_path": pdf_path,
            "row_count": len(cleaned_df),
            "column_count": len(cleaned_df.columns),
            "target_column": target_column,
            "task_type": model_results["task_type"],
        }

        job_store.set_result(job_id, to_json_safe(result))
        job_store.update_status(job_id, "complete")

    except Exception as exc:
        error_message = _extract_error_message(exc)
        logger.error("Job %s failed: %s", job_id, error_message)
        job_store.update_status(job_id, "failed", error=error_message)


def _extract_error_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)

    if isinstance(detail, dict):
        return detail.get("error", str(detail))

    if isinstance(detail, str):
        return detail

    return str(exc)
