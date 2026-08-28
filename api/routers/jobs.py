# api/routers/jobs.py

import copy

from fastapi import APIRouter, HTTPException

from api.job_store import job_store
from api.services.plan_guard import PLAN_LIMITS

router = APIRouter()


@router.get("/jobs/{job_id}/status")
def get_job_status(job_id: str):
    job = job_store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": job["progress"],
        "error": job["error"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
    }


@router.get("/jobs/{job_id}/result")
def get_job_result(job_id: str):
    job = job_store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "complete":
        return {
            "status": job["status"],
            "progress": job["progress"],
            "message": "Not ready yet",
        }

    result = copy.deepcopy(job["result"])
    plan = job["plan"]
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])

    if not limits["shap_access"]:
        result["explanations"] = {
            "locked": True,
            "message": "Upgrade to Starter or Pro to unlock SHAP feature explanations.",
        }

    if not limits["ai_summary"]:
        result["executive_summary"] = None
        result["executive_summary_locked"] = True

    return result
