# run.py

import argparse
import sys

from core.pipeline import Pipeline
from reporting.html_generator import HTMLReportGenerator
from reporting.pdf_generator import PDFReportGenerator
from utils.file_handler import load_dataset


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="AI Business Analytics System"
    )

    parser.add_argument(
        "--file", type=str, required=True, help="Path to dataset (CSV/XLSX)"
    )
    parser.add_argument(
        "--target", type=str, required=True, help="Target column name"
    )

    args = parser.parse_args()

    config = {}

    # Step 1: Load data
    df = load_dataset(args.file)

    # Step 2: Run pipeline
    pipeline = Pipeline(config)
    results = pipeline.run(df, args.target)

    report_data = results["report"]

    # Step 3: Generate HTML
    html_generator = HTMLReportGenerator()
    html_path = html_generator.generate(report_data)

    # Step 4: Generate PDF
    pdf_generator = PDFReportGenerator()
    pdf_path = pdf_generator.generate(report_data)

    # Step 5: Output
    print("\n✅ Pipeline executed successfully!")
    print(f"📄 HTML Report: {html_path}")
    print(f"📑 PDF Report: {pdf_path}")


if __name__ == "__main__":
    main()