# api/routers/report.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.job_store import job_store
from api.services.plan_guard import PLAN_LIMITS

router = APIRouter()


def _get_completed_job(job_id: str) -> dict:
    job = job_store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "complete":
        raise HTTPException(status_code=409, detail="Report not ready yet")

    return job


@router.get("/jobs/{job_id}/report/html")
def get_html_report(job_id: str):
    job = _get_completed_job(job_id)

    return FileResponse(
        job["result"]["report_html_path"],
        media_type="text/html",
        filename="report.html",
    )


@router.get("/jobs/{job_id}/report/pdf")
def get_pdf_report(job_id: str):
    job = _get_completed_job(job_id)

    limits = PLAN_LIMITS.get(job["plan"], PLAN_LIMITS["free"])

    if not limits["pdf_report"]:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PDF reports require a paid plan",
                "upgrade_to": "starter",
            },
        )

    return FileResponse(
        job["result"]["report_pdf_path"],
        media_type="application/pdf",
        filename="report.pdf",
    )
