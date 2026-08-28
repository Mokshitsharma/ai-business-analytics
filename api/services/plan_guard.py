# api/services/plan_guard.py

import jwt
import pandas as pd
from fastapi import HTTPException, Request

from configs.settings import ENVIRONMENT, JWT_SECRET
from utils.logger import get_logger

logger = get_logger(__name__)

PLAN_LIMITS = {
    "free": {
        "max_file_size_mb": 5,
        "max_rows": 1000,
        "analyses_per_month": 1,
        "pdf_report": False,
        "shap_access": False,
        "ai_summary": False,
    },
    "starter": {
        "max_file_size_mb": 50,
        "max_rows": 50000,
        "analyses_per_month": 10,
        "pdf_report": True,
        "shap_access": True,
        "ai_summary": True,
    },
    "pro": {
        "max_file_size_mb": 500,
        "max_rows": 500000,
        "analyses_per_month": -1,
        "pdf_report": True,
        "shap_access": True,
        "ai_summary": True,
    },
}


def get_plan(request: Request) -> str:
    """
    Resolves the caller's plan.
    In development, every request is treated as "pro" so the full
    feature set can be exercised without a real auth/billing system.
    In production, the plan is read from a "plan" claim on a bearer JWT,
    falling back to "free" if the token is missing or invalid.
    """

    if ENVIRONMENT != "production":
        return "pro"

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return "free"

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        plan = payload.get("plan", "free")
    except jwt.PyJWTError as exc:
        logger.warning("JWT verification failed: %s", exc)
        return "free"

    return plan if plan in PLAN_LIMITS else "free"


def check_row_limit(df: pd.DataFrame, plan: str) -> None:
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    row_count = len(df)

    if row_count > limits["max_rows"]:
        upgrade_to = "starter" if plan == "free" else "pro"

        raise HTTPException(
            status_code=403,
            detail={
                "error": "Row limit exceeded",
                "limit": limits["max_rows"],
                "your_rows": row_count,
                "upgrade_to": upgrade_to,
            },
        )
