# core/pipeline.py

import pandas as pd

from core.preprocessing.cleaner import DataCleaner
from core.eda.analyzer import EDAAnalyzer
from core.features.engineer import FeatureEngineer
from core.models.trainer import ModelTrainer
from core.xai.shap_explainer import ShapExplainer
from core.insights.generator import InsightGenerator
from reporting.report_builder import ReportBuilder


class Pipeline:
    """
    End-to-end pipeline:
    Clean -> EDA -> Feature Engineer -> Train -> Explain -> Insights -> Report
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

        self.cleaner = DataCleaner()
        self.eda_analyzer = EDAAnalyzer()
        self.feature_engineer = FeatureEngineer()
        self.trainer = ModelTrainer()
        self.explainer = ShapExplainer()
        self.insight_generator = InsightGenerator()
        self.report_builder = ReportBuilder()

        self.model = None

    def run(self, df: pd.DataFrame, target_column: str) -> dict:
        # 1. Clean
        df = self.cleaner.clean(df)

        # 2. EDA
        eda_results = self.eda_analyzer.analyze(df)

        # 3. Feature engineering (splits X/y internally)
        X, y = self.feature_engineer.transform(df, target_column)

        # 4. Train
        train_result = self.trainer.train(X, y)
        self.model = train_result["model"]
        metrics = train_result["metrics"]
        metrics["task_type"] = train_result["task_type"]

        # 5. Explainability (best-effort; must not break the report)
        try:
            explanations = self.explainer.explain(self.model, X)
        except Exception as exc:
            explanations = {"error": str(exc)}

        # 6. Business insights
        predictions = self.model.predict(X)
        insights = self.insight_generator.generate(df, predictions)

        # 7. Final report (includes LLM executive summary)
        report = self.report_builder.build(
            eda_results=eda_results,
            metrics=metrics,
            insights=insights,
            explanations=explanations,
        )

        return {
            "model": self.model,
            "report": report,
        }
