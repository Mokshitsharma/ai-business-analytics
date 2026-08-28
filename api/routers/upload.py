# api/routers/upload.py

import threading

from fastapi import APIRouter, File, Form, Request, UploadFile

from api.job_store import job_store
from api.services.file_handler import save_upload, validate_file
from api.services.job_runner import run_analysis_job
from api.services.plan_guard import get_plan

router = APIRouter()


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    target_column: str = Form(""),
):
    # Plan is derived from the caller's identity, never trusted from the client.
    # In non-production every caller is treated as "pro" (see plan_guard.get_plan).
    plan = get_plan(request)

    validate_file(file, plan)

    job_id = job_store.create_job(
        filename=file.filename, target_column=target_column, plan=plan
    )

    file_path = save_upload(file, job_id)

    thread = threading.Thread(
        target=run_analysis_job,
        args=(job_id, str(file_path), target_column, plan),
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Analysis started",
        "estimated_seconds": 45,
        "poll_url": f"/jobs/{job_id}/status",
    }
