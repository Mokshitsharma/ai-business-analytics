# core/preprocessing/cleaner.py

from typing import Dict
import pandas as pd
import numpy as np


class DataCleaner:
    """Handles data cleaning: duplicates, missing values, type detection."""

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df = self._remove_duplicates(df)
        column_types = self._detect_column_types(df)
        df = self._handle_missing_values(df, column_types)
        df = self._fix_dtypes(df, column_types)

        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates()

    def _detect_column_types(self, df: pd.DataFrame) -> Dict[str, str]:
        column_types = {}

        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                column_types[col] = "numerical"

            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                column_types[col] = "datetime"

            else:
                unique_ratio = df[col].nunique() / len(df)

                if unique_ratio < 0.05:
                    column_types[col] = "categorical"
                else:
                    column_types[col] = "text"

        return column_types

    def _handle_missing_values(
        self, df: pd.DataFrame, column_types: Dict[str, str]
    ) -> pd.DataFrame:

        for col, col_type in column_types.items():

            if df[col].isnull().sum() == 0:
                continue

            if col_type == "numerical":
                df[col] = df[col].fillna(df[col].median())

            elif col_type == "categorical":
                df[col] = df[col].fillna(df[col].mode()[0])

            elif col_type == "datetime":
                df[col] = df[col].ffill().bfill()

            else:  # text
                df[col] = df[col].fillna("unknown")

        return df

    def _fix_dtypes(
        self, df: pd.DataFrame, column_types: Dict[str, str]
    ) -> pd.DataFrame:

        for col, col_type in column_types.items():

            if col_type == "datetime":
                df[col] = pd.to_datetime(df[col], errors="coerce")

            elif col_type == "numerical":
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df