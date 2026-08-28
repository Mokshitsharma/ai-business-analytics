# core/features/engineer.py

from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Categorical columns with more distinct values than this are dropped rather
# than one-hot encoded - they are usually IDs, free text or raw timestamps
# and would explode the feature space.
MAX_CATEGORICAL_CARDINALITY = 40


class FeatureEngineer:
    """Transforms raw data into ML-ready features."""

    def __init__(self):
        self.pipeline = None
        self.numeric_cols: List[str] = []
        self.categorical_cols: List[str] = []
        self.dropped_cols: List[str] = []

    def transform(
        self, df: pd.DataFrame, target_column: str
    ) -> Tuple[pd.DataFrame, pd.Series]:

        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found")

        df = df.copy()

        y = df[target_column]
        X = df.drop(columns=[target_column])

        X = self._expand_datetime_columns(X)
        X, self.dropped_cols = self._drop_unusable_columns(X)

        self.numeric_cols = X.select_dtypes(include=np.number).columns.tolist()
        self.categorical_cols = X.select_dtypes(exclude=np.number).columns.tolist()

        self.pipeline = self._build_pipeline()

        X_transformed = self.pipeline.fit_transform(X)
        feature_names = self._get_feature_names()

        X_final = pd.DataFrame(
            X_transformed, columns=feature_names, index=X.index
        )

        return X_final, y

    # ------------------------------------------------------------------
    # Column preparation
    # ------------------------------------------------------------------
    def _expand_datetime_columns(self, X: pd.DataFrame) -> pd.DataFrame:
        """Turn datetime (or date-like string) columns into numeric parts."""

        for col in list(X.columns):
            series = X[col]

            if not pd.api.types.is_datetime64_any_dtype(series):
                if series.dtype != "object":
                    continue
                parsed = pd.to_datetime(series, errors="coerce")
                # Only treat as a date column if most values parsed.
                if parsed.notna().mean() < 0.8:
                    continue
                series = parsed

            X[f"{col}_year"] = series.dt.year
            X[f"{col}_month"] = series.dt.month
            X[f"{col}_day"] = series.dt.day
            X[f"{col}_dayofweek"] = series.dt.dayofweek
            X = X.drop(columns=[col])

        return X

    def _drop_unusable_columns(
        self, X: pd.DataFrame
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Drop high-cardinality categoricals (IDs, free text)."""

        dropped = []

        for col in X.select_dtypes(exclude=np.number).columns:
            if X[col].nunique(dropna=False) > MAX_CATEGORICAL_CARDINALITY:
                dropped.append(col)

        if dropped:
            X = X.drop(columns=dropped)

        return X, dropped

    # ------------------------------------------------------------------
    # Sklearn pipeline
    # ------------------------------------------------------------------
    def _build_pipeline(self) -> ColumnTransformer:
        numeric_pipeline = Pipeline(steps=[("scaler", StandardScaler())])

        categorical_pipeline = Pipeline(
            steps=[
                ("encoder", OneHotEncoder(
                    handle_unknown="ignore", sparse_output=False
                ))
            ]
        )

        return ColumnTransformer(
            transformers=[
                ("num", numeric_pipeline, self.numeric_cols),
                ("cat", categorical_pipeline, self.categorical_cols),
            ]
        )

    def _get_feature_names(self) -> List[str]:
        feature_names = list(self.numeric_cols)

        if self.categorical_cols:
            encoder = self.pipeline.named_transformers_["cat"]["encoder"]
            cat_names = encoder.get_feature_names_out(self.categorical_cols)
            feature_names.extend(cat_names.tolist())

        return feature_names
