# core/models/trainer.py

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error, r2_score
import pandas as pd
import numpy as np


class ModelTrainer:
    """
    Auto ML Trainer:
    - Detects classification vs regression
    - Handles small datasets safely
    - Dynamically adjusts cross-validation
    """

    def __init__(self):
        self.model = None
        self.task_type = None

    # -----------------------------
    # Detect problem type
    # -----------------------------
    def detect_task(self, y: pd.Series):
        if y.dtype == "object" or y.nunique() <= 10:
            return "classification"
        return "regression"

    # -----------------------------
    # Safe CV generator
    # -----------------------------
    def get_cv(self, y: pd.Series, max_splits=5):
        min_class = y.value_counts().min()

        if min_class < 2:
            return None

        n_splits = min(max_splits, min_class)

        if n_splits < 2:
            return None

        return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    # -----------------------------
    # Train model
    # -----------------------------
    def train(self, X: pd.DataFrame, y: pd.Series):
        self.task_type = self.detect_task(y)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # -------------------------
        # Model selection
        # -------------------------
        if self.task_type == "classification":
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)

        # -------------------------
        # Fit model
        # -------------------------
        self.model.fit(X_train, y_train)

        # -------------------------
        # Predictions
        # -------------------------
        y_pred = self.model.predict(X_test)

        # -------------------------
        # Metrics
        # -------------------------
        if self.task_type == "classification":
            metrics = {
                "accuracy": accuracy_score(y_test, y_pred),
                "f1_score": f1_score(y_test, y_pred, average="weighted"),
            }
        else:
            metrics = {
                "rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
                "r2_score": r2_score(y_test, y_pred),
            }

        # -------------------------
        # Cross-validation (SAFE)
        # -------------------------
        cv = self.get_cv(y)

        if cv is not None:
            try:
                scores = cross_val_score(self.model, X, y, cv=cv)
                metrics["cv_score"] = float(np.mean(scores))
            except Exception:
                metrics["cv_score"] = None
        else:
            metrics["cv_score"] = None

        return {
            "model": self.model,
            "metrics": metrics,
            "task_type": self.task_type
        }