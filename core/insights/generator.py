# core/insights/generator.py

from typing import Dict, Any, List
import pandas as pd
import numpy as np


class InsightGenerator:
    """Generates business insights from data and predictions."""

    def generate(
        self, df: pd.DataFrame, predictions: np.ndarray
    ) -> Dict[str, Any]:

        return {
            "trends": self._detect_trends(df),
            "anomalies": self._detect_anomalies(df),
            "segments": self._segment_analysis(df),
            "predictions": self._prediction_insights(predictions),
        }

    def _detect_trends(self, df: pd.DataFrame) -> List[str]:
        insights = []

        numeric_cols = df.select_dtypes(include=np.number).columns

        for col in numeric_cols:
            if len(df[col]) < 5:
                continue

            trend = df[col].rolling(window=5).mean()

            if trend.iloc[-1] > trend.iloc[0]:
                insights.append(f"{col} shows an increasing trend")

            elif trend.iloc[-1] < trend.iloc[0]:
                insights.append(f"{col} shows a decreasing trend")

        return insights

    def _detect_anomalies(self, df: pd.DataFrame) -> List[str]:
        insights = []

        numeric_cols = df.select_dtypes(include=np.number).columns

        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1

            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR

            outliers = df[(df[col] < lower) | (df[col] > upper)]

            if len(outliers) > 0:
                insights.append(
                    f"{col} has {len(outliers)} potential anomalies"
                )

        return insights

    def _segment_analysis(self, df: pd.DataFrame) -> List[str]:
        insights = []

        categorical_cols = df.select_dtypes(exclude=np.number).columns
        numeric_cols = df.select_dtypes(include=np.number).columns

        for cat_col in categorical_cols:
            for num_col in numeric_cols:
                grouped = df.groupby(cat_col)[num_col].mean()

                if len(grouped) < 2:
                    continue

                top = grouped.idxmax()
                bottom = grouped.idxmin()

                insights.append(
                    f"{top} has highest {num_col}, {bottom} has lowest"
                )

        return insights

    def _prediction_insights(
        self, predictions: np.ndarray
    ) -> Dict[str, Any]:

        predictions = np.asarray(predictions)

        if not np.issubdtype(predictions.dtype, np.number):
            # Classification with non-numeric labels: report class balance.
            values, counts = np.unique(predictions, return_counts=True)
            return {
                "class_distribution": {
                    str(v): int(c) for v, c in zip(values, counts)
                }
            }

        return {
            "mean_prediction": float(np.mean(predictions)),
            "min_prediction": float(np.min(predictions)),
            "max_prediction": float(np.max(predictions)),
        }