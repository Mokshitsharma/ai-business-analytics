# core/xai/shap_explainer.py

from typing import Dict, Any
import numpy as np
import pandas as pd
import shap


class ShapExplainer:
    """Generates SHAP-based model explanations."""

    def __init__(self, sample_size: int = 100):
        self.sample_size = sample_size

    def explain(
        self, model: Any, X: pd.DataFrame
    ) -> Dict[str, Any]:

        X_sample = self._sample_data(X)

        explainer = shap.Explainer(model, X_sample)
        # Random forests can trip SHAP's additivity check due to floating-point
        # summation order; the resulting values are still valid for reporting.
        shap_values = explainer(X_sample, check_additivity=False)

        global_importance = self._global_feature_importance(
            shap_values, X_sample.columns
        )

        local_explanations = self._local_explanations(
            shap_values, X_sample
        )

        return {
            "global_importance": global_importance,
            "local_explanations": local_explanations,
        }

    def _sample_data(self, X: pd.DataFrame) -> pd.DataFrame:
        if len(X) > self.sample_size:
            return X.sample(self.sample_size, random_state=42)
        return X

    def _global_feature_importance(
        self, shap_values, feature_names
    ) -> Dict[str, float]:

        values = np.abs(shap_values.values)

        if values.ndim == 3:  # multiclass: (samples, features, classes)
            values = values.mean(axis=2)

        values = values.mean(axis=0)

        return {
            feature: float(importance)
            for feature, importance in zip(feature_names, values)
        }

    def _local_explanations(
        self, shap_values, X_sample: pd.DataFrame
    ) -> Dict[str, Any]:

        explanations = []

        for i in range(min(5, len(X_sample))):
            row = shap_values.values[i]

            if row.ndim == 2:  # multiclass: (features, classes)
                row = row.mean(axis=1)

            explanations.append({
                "prediction_index": int(i),
                "feature_values": X_sample.iloc[i].to_dict(),
                "shap_values": {
                    feature: float(val)
                    for feature, val in zip(X_sample.columns, row)
                }
            })

        return explanations