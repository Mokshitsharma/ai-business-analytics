# core/utils/cv.py

from sklearn.model_selection import StratifiedKFold


def get_safe_cv(y, max_splits=5):
    """
    Global safe CV:
    Never crashes even on tiny datasets.
    """

    min_class = y.value_counts().min()

    if min_class < 2:
        return None

    n_splits = min(max_splits, min_class)

    if n_splits < 2:
        return None

    return StratifiedKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=42
    )