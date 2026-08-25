# core/models/evaluator.py

import numpy as np
from sklearn.model_selection import cross_val_score
from utils.cv import get_safe_cv


class ModelEvaluator:

    def evaluate(self, model, X, y):
        cv = get_safe_cv(y)

        results = {}

        if cv is None:
            results["cv_score"] = None
            return results

        try:
            scores = cross_val_score(model, X, y, cv=cv)
            results["cv_score"] = float(np.mean(scores))
        except Exception:
            results["cv_score"] = None

        return results