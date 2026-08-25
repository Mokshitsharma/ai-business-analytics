# llm/summarizer.py

from typing import Dict, Any
from llm.client import LLMClient
from llm.prompt_templates import build_summary_prompt


class LLMSummarizer:
    """Generates executive summary using LLM."""

    def __init__(self):
        self.client = LLMClient()

    def summarize(self, context: Dict[str, Any]) -> str:
        prompt = build_summary_prompt(context)

        try:
            response = self.client.generate(prompt)
            return response.strip()
        except Exception:
            return self._fallback_summary(context)

    def _fallback_summary(self, context: Dict[str, Any]) -> str:
        metrics = context.get("metrics", {})
        insights = context.get("insights", {})

        return (
            "Summary:\n"
            f"- Key metrics: {metrics}\n"
            f"- Insights: {insights}\n"
            "LLM unavailable, showing structured summary."
        )