# api/services/file_handler.py

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile

from api.services.plan_guard import PLAN_LIMITS
from configs.settings import UPLOADS_DIR

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}


def validate_file(file: UploadFile, plan: str) -> dict:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file.file.seek(0, 2)  # seek to end
    size_bytes = file.file.tell()
    file.file.seek(0)  # rewind for downstream reads

    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    max_bytes = limits["max_file_size_mb"] * 1024 * 1024

    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_bytes / (1024 * 1024):.1f}MB). "
            f"Max for '{plan}' plan is {limits['max_file_size_mb']}MB.",
        )

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    return {
        "filename": filename,
        "extension": extension,
        "size_bytes": size_bytes,
    }


def save_upload(file: UploadFile, job_id: str) -> Path:
    upload_dir = Path(UPLOADS_DIR) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / file.filename
    file.file.seek(0)

    with open(file_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    return file_path
