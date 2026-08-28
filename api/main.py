# api/main.py

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.routers import health, jobs, report, upload
from configs.settings import ENVIRONMENT, OUTPUTS_DIR, UPLOADS_DIR

app = FastAPI(
    title="AI Business Analytics API",
    version="1.0.0",
    description="Upload a dataset, get an automated ML analysis and report.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _ensure_dirs() -> None:
    for d in (UPLOADS_DIR, OUTPUTS_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Normalise error responses to a consistent envelope."""
    detail = exc.detail

    if isinstance(detail, dict):
        body = {"error": detail.get("error", "request_failed"), **detail}
    else:
        body = {"error": str(detail)}

    return JSONResponse(status_code=exc.status_code, content=body)


# API routes
app.include_router(health.router, tags=["health"])
app.include_router(upload.router, tags=["analysis"])
app.include_router(jobs.router, tags=["analysis"])
app.include_router(report.router, tags=["analysis"])


@app.get("/meta")
def meta():
    return {"environment": ENVIRONMENT, "service": "ai-business-analytics"}


# Static frontend (built separately). Mounted last so it never shadows the API.
_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="frontend")
