# reporting/html_generator.py

from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader
import os


class HTMLReportGenerator:
    """Generates HTML report using Jinja2 templates."""

    def __init__(self, template_dir: str = "reporting/templates"):
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )

    def generate(
        self,
        report_data: Dict[str, Any],
        output_path: str = "data/outputs/report.html"
    ) -> str:

        template = self.env.get_template("report.html")

        html_content = template.render(report=report_data)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path