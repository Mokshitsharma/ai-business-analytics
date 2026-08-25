# core/eda/analyzer.py

from typing import Dict, Any
import pandas as pd
import numpy as np


class EDAAnalyzer:
    """Performs exploratory data analysis and returns structured insights."""

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        return {
            "summary_stats": self._summary_statistics(df),
            "correlations": self._correlation_analysis(df),
            "distributions": self._distribution_analysis(df),
            "trends": self._trend_detection(df),
            "data_quality": self._data_quality_report(df),
        }

    def _summary_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        return df.describe(include="all").to_dict()

    def _correlation_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        numeric_df = df.select_dtypes(include=np.number)

        if numeric_df.empty:
            return {}

        corr_matrix = numeric_df.corr()

        return {
            "correlation_matrix": corr_matrix.to_dict(),
            "high_correlations": self._get_high_correlations(corr_matrix),
        }

    def _get_high_correlations(
        self, corr_matrix: pd.DataFrame, threshold: float = 0.7
    ) -> Dict[str, float]:

        high_corr = {}

        for i in range(len(corr_matrix.columns)):
            for j in range(i):
                val = corr_matrix.iloc[i, j]
                if abs(val) > threshold:
                    col1 = corr_matrix.columns[i]
                    col2 = corr_matrix.columns[j]
                    high_corr[f"{col1}__{col2}"] = float(val)

        return high_corr

    def _distribution_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        distributions = {}

        numeric_cols = df.select_dtypes(include=np.number).columns

        for col in numeric_cols:
            distributions[col] = {
                "mean": float(df[col].mean()),
                "median": float(df[col].median()),
                "std": float(df[col].std()),
                "skew": float(df[col].skew()),
                "kurtosis": float(df[col].kurtosis()),
            }

        return distributions

    def _trend_detection(self, df: pd.DataFrame) -> Dict[str, Any]:
        trends = {}

        datetime_cols = df.select_dtypes(include=["datetime64[ns]"]).columns
        numeric_cols = df.select_dtypes(include=np.number).columns

        for dt_col in datetime_cols:
            df_sorted = df.sort_values(by=dt_col)

            for num_col in numeric_cols:
                rolling_mean = (
                    df_sorted[num_col].rolling(window=5).mean().dropna()
                )

                if not rolling_mean.empty:
                    trend = rolling_mean.iloc[-1] - rolling_mean.iloc[0]

                    trends[f"{num_col}_over_{dt_col}"] = float(trend)

        return trends

    def _data_quality_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        return {
            "missing_values": df.isnull().sum().to_dict(),
            "duplicate_rows": int(df.duplicated().sum()),
            "num_rows": int(df.shape[0]),
            "num_columns": int(df.shape[1]),
        }