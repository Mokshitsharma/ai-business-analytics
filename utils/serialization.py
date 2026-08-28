# utils/serialization.py

import math
from typing import Any

import numpy as np


def to_json_safe(obj: Any) -> Any:
    """
    Recursively convert a value into something the stdlib JSON encoder
    accepts: numpy scalars/arrays become plain Python, and NaN / +-inf
    (which are not valid JSON) become None.
    """
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [to_json_safe(v) for v in obj]

    if isinstance(obj, np.ndarray):
        return [to_json_safe(v) for v in obj.tolist()]

    if isinstance(obj, np.generic):
        obj = obj.item()

    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None

    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj

    # Fall back to a string for anything exotic (timestamps, etc.)
    return str(obj)
