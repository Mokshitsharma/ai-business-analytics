# app/main.py

import streamlit as st
import pandas as pd
import tempfile
import os

from core.pipeline import Pipeline
from reporting.html_generator import HTMLReportGenerator
from reporting.pdf_generator import PDFReportGenerator


# -----------------------------
# Streamlit Config
# -----------------------------
st.set_page_config(page_title="AI Business Analytics", layout="wide")

st.title("📊 AI Business Analytics System")
st.write("Upload your dataset and get ML insights, predictions, and reports.")


# -----------------------------
# File Loader (FIXED)
# -----------------------------
def load_data(uploaded_file):
    file_extension = uploaded_file.name.split(".")[-1].lower()

    if file_extension not in ["csv", "xlsx", "xls"]:
        raise ValueError("Unsupported file format. Please upload CSV or Excel only.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp:
        tmp.write(uploaded_file.read())
        temp_path = tmp.name

    if file_extension == "csv":
        df = pd.read_csv(temp_path)

    else:
        df = pd.read_excel(temp_path)

    return df, temp_path


# -----------------------------
# Upload Section
# -----------------------------
uploaded_file = st.file_uploader(
    "Upload dataset (CSV / Excel)",
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is not None:

    try:
        df, file_path = load_data(uploaded_file)

        st.subheader("📂 Data Preview")
        st.dataframe(df.head())

        # Target selection
        target_column = st.selectbox("🎯 Select Target Column", df.columns)

        # Run pipeline
        if st.button("🚀 Run Analysis"):

            with st.spinner("Running AI pipeline... please wait"):

                pipeline = Pipeline(config={})
                results = pipeline.run(df, target_column)

                report_data = results["report"]

                # -----------------------------
                # Generate HTML report
                # -----------------------------
                html_gen = HTMLReportGenerator()
                html_path = html_gen.generate(report_data)

                # -----------------------------
                # Generate PDF report
                # -----------------------------
                pdf_gen = PDFReportGenerator()
                pdf_path = pdf_gen.generate(report_data)

                # -----------------------------
                # UI OUTPUT
                # -----------------------------
                st.success("Analysis Completed Successfully!")

                st.subheader("🧠 Executive Summary")
                st.write(report_data.get("executive_summary", ""))

                st.subheader("📊 Metrics")
                st.json(report_data.get("metrics", {}))

                st.subheader("💡 Insights")
                st.json(report_data.get("insights", {}))

                # -----------------------------
                # Download Buttons
                # -----------------------------
                col1, col2 = st.columns(2)

                with open(html_path, "rb") as f:
                    col1.download_button(
                        "⬇️ Download HTML Report",
                        f,
                        file_name="report.html"
                    )

                with open(pdf_path, "rb") as f:
                    col2.download_button(
                        "⬇️ Download PDF Report",
                        f,
                        file_name="report.pdf"
                    )

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

    finally:
        # Cleanup temp file
        if "file_path" in locals() and os.path.exists(file_path):
            os.remove(file_path)