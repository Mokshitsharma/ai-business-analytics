# reporting/report_builder.py

from typing import Dict, Any
from llm.summarizer import LLMSummarizer


class ReportBuilder:
    """Builds structured report from pipeline outputs."""

    def __init__(self):
        self.summarizer = LLMSummarizer()

    def build(
        self,
        eda_results: Dict[str, Any],
        metrics: Dict[str, Any],
        insights: Dict[str, Any],
        explanations: Dict[str, Any],
    ) -> Dict[str, Any]:

        context = {
            "eda": eda_results,
            "metrics": metrics,
            "insights": insights,
        }

        summary = self.summarizer.summarize(context)

        report = {
            "executive_summary": summary,
            "metrics": metrics,
            "insights": insights,
            "eda": eda_results,
            "explanations": explanations,
        }

        return report