# llm/prompt_templates.py

from typing import Dict, Any
import json


def build_summary_prompt(context: Dict[str, Any]) -> str:
    """Builds a structured prompt for executive summary."""

    metrics = context.get("metrics", {})
    insights = context.get("insights", {})
    eda = context.get("eda", {})

    prompt = f"""
You are a senior business analyst.

Analyze the following data and generate a concise executive summary.

DATA:
- Metrics:
{json.dumps(metrics, indent=2)}

- Insights:
{json.dumps(insights, indent=2)}

- EDA Summary:
{_extract_eda_highlights(eda)}

INSTRUCTIONS:
1. Summarize key findings
2. Explain possible reasons behind trends
3. Highlight risks or anomalies
4. Provide actionable business recommendations

OUTPUT FORMAT:
- Executive Summary (short paragraph)
- Key Insights (bullet points)
- Recommendations (bullet points)

Keep it concise, clear, and business-focused.
Avoid technical jargon.
"""
    return prompt.strip()


def _extract_eda_highlights(eda: Dict[str, Any]) -> str:
    """Extracts minimal useful EDA info to avoid prompt overload."""

    if not eda:
        return "No EDA data available"

    summary = {}

    # Only include high-value info
    if "data_quality" in eda:
        summary["data_quality"] = eda["data_quality"]

    if "correlations" in eda:
        summary["high_correlations"] = eda["correlations"].get(
            "high_correlations", {}
        )

    return json.dumps(summary, indent=2)