# core/features/engineer.py

from typing import Tuple, List
import pandas as pd
import numpy as np

from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline


class FeatureEngineer:
    """Transforms raw data into ML-ready features."""

    def __init__(self):
        self.pipeline = None
        self.numeric_cols: List[str] = []
        self.categorical_cols: List[str] = []

    def transform(
        self, df: pd.DataFrame, target_column: str
    ) -> Tuple[pd.DataFrame, pd.Series]:

        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found")

        df = df.copy()

        y = df[target_column]
        X = df.drop(columns=[target_column])

        self.numeric_cols = X.select_dtypes(include=np.number).columns.tolist()
        self.categorical_cols = X.select_dtypes(
            exclude=np.number
        ).columns.tolist()

        self.pipeline = self._build_pipeline()

        X_transformed = self.pipeline.fit_transform(X)

        feature_names = self._get_feature_names()

        X_final = pd.DataFrame(
            X_transformed, columns=feature_names, index=X.index
        )

        return X_final, y

    def _build_pipeline(self) -> ColumnTransformer:
        numeric_pipeline = Pipeline(
            steps=[
                ("scaler", StandardScaler())
            ]
        )

        categorical_pipeline = Pipeline(
            steps=[
                ("encoder", OneHotEncoder(handle_unknown="ignore"))
            ]
        )

        return ColumnTransformer(
            transformers=[
                ("num", numeric_pipeline, self.numeric_cols),
                ("cat", categorical_pipeline, self.categorical_cols),
            ]
        )

    def _get_feature_names(self) -> List[str]:
        feature_names = []

        if self.numeric_cols:
            feature_names.extend(self.numeric_cols)

        if self.categorical_cols:
            encoder = self.pipeline.named_transformers_["cat"][
                "encoder"
            ]
            cat_names = encoder.get_feature_names_out(self.categorical_cols)
            feature_names.extend(cat_names.tolist())

        return feature_names