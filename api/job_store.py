# api/job_store.py

import threading
import time
import uuid
from typing import Optional

PROGRESS_BY_STATUS = {
    "queued": 0,
    "cleaning": 10,
    "analyzing": 30,
    "modeling": 50,
    "explaining": 65,
    "generating_insights": 80,
    "generating_report": 90,
    "complete": 100,
}


class JobStore:
    """In-memory job tracker. No database needed."""

    def __init__(self):
        self._jobs: dict = {}
        self._lock = threading.Lock()

    def create_job(self, filename: str, target_column: str, plan: str) -> str:
        job_id = str(uuid.uuid4())

        job = {
            "job_id": job_id,
            "filename": filename,
            "target_column": target_column,
            "plan": plan,
            "status": "queued",
            "progress": PROGRESS_BY_STATUS["queued"],
            "error": None,
            "result": None,
            "created_at": time.time(),
            "completed_at": None,
        }

        with self._lock:
            self._jobs[job_id] = job

        return job_id

    def update_status(self, job_id: str, status: str, error: Optional[str] = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)

            if job is None:
                return

            job["status"] = status

            if status == "failed":
                job["error"] = error
                job["completed_at"] = time.time()
            else:
                job["progress"] = PROGRESS_BY_STATUS.get(status, job["progress"])

                if status == "complete":
                    job["completed_at"] = time.time()

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job is not None else None

    def set_result(self, job_id: str, result_dict: dict) -> None:
        with self._lock:
            job = self._jobs.get(job_id)

            if job is not None:
                job["result"] = result_dict


job_store = JobStore()
