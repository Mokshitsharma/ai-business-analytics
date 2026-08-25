# reporting/pdf_generator.py

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from typing import Dict, Any
import os


class PDFReportGenerator:
    """Generates PDF report using ReportLab (no external deps)."""

    def generate(
        self,
        report_data: Dict[str, Any],
        output_path: str = "data/outputs/report.pdf"
    ) -> str:

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        doc = SimpleDocTemplate(output_path)
        styles = getSampleStyleSheet()

        content = []

        # Title
        content.append(Paragraph("AI Business Analytics Report", styles["Title"]))
        content.append(Spacer(1, 12))

        # Summary
        content.append(Paragraph("Executive Summary", styles["Heading2"]))
        content.append(Paragraph(report_data["executive_summary"], styles["BodyText"]))
        content.append(Spacer(1, 12))

        # Metrics
        content.append(Paragraph("Metrics", styles["Heading2"]))
        for k, v in report_data["metrics"].items():
            content.append(Paragraph(f"{k}: {v}", styles["BodyText"]))
        content.append(Spacer(1, 12))

        # Insights
        content.append(Paragraph("Insights", styles["Heading2"]))
        for section, items in report_data["insights"].items():
            content.append(Paragraph(section, styles["Heading3"]))
            if isinstance(items, list):
                for item in items:
                    content.append(Paragraph(f"- {item}", styles["BodyText"]))
        content.append(Spacer(1, 12))

        doc.build(content)

        return output_path