# llm/summarizer.py

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from llm.client import LLMClient
from llm.prompt_templates import build_summary_prompt

# Hard wall-clock cap on producing the executive summary. If the LLM call
# hangs or errors, the report still ships with a structured fallback.
_SUMMARY_DEADLINE_SECONDS = 30
_executor = ThreadPoolExecutor(max_workers=2)


class LLMSummarizer:
    """Generates an executive summary using an LLM, with a safe fallback."""

    def __init__(self):
        # Created lazily so a missing/invalid API key never breaks report
        # assembly - it just falls back to the structured summary.
        self._client: Optional[LLMClient] = None

    def _get_client(self) -> LLMClient:
        if self._client is None:
            self._client = LLMClient()
        return self._client

    def summarize(self, context: Dict[str, Any]) -> str:
        prompt = build_summary_prompt(context)

        try:
            future = _executor.submit(self._get_client().generate, prompt)
            return future.result(timeout=_SUMMARY_DEADLINE_SECONDS).strip()
        except Exception:
            return self._fallback_summary(context)

    def _fallback_summary(self, context: Dict[str, Any]) -> str:
        """Concise, readable summary used when the LLM is unavailable."""
        metrics = context.get("metrics", {}) or {}
        insights = context.get("insights", {}) or {}

        task = metrics.get("task_type", "model")
        if "accuracy" in metrics:
            headline = f"accuracy of {metrics['accuracy']:.1%}"
        elif "r2_score" in metrics:
            headline = f"an R² of {metrics['r2_score']:.2f}"
        else:
            headline = "the metrics below"

        lines = [
            f"A {task} model was trained and reached {headline}. "
            "The AI executive summary is unavailable right now, so this is a "
            "structured recap of the findings.",
        ]

        def _bullets(title: str, items: Any, limit: int = 4) -> None:
            if isinstance(items, list) and items:
                lines.append("")
                lines.append(f"{title}:")
                for item in items[:limit]:
                    lines.append(f"  • {item}")
                if len(items) > limit:
                    lines.append(f"  • …and {len(items) - limit} more")

        _bullets("Trends", insights.get("trends"))
        _bullets("Anomalies", insights.get("anomalies"))
        _bullets("Segments", insights.get("segments"))

        return "\n".join(lines)
