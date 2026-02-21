"""
SIGNAL Backend — FastAPI app entry point (company profile + brand intake).
Run from repo root with PYTHONPATH=code:  uvicorn backend.main:app --reload --port 8000
Or from code/backend with PYTHONPATH=code:  python -m uvicorn backend.main:app --reload --port 8000
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from backend.routers import company
from backend.routers import jobs as jobs_router
from backend.routers import signals as signals_router
from backend.routers import campaigns as campaigns_router
from backend.routers import content as content_router
from backend.routers import feedback as feedback_router
from backend.feedback_scheduler import create_feedback_scheduler
from backend.config import settings


@asynccontextmanager
async def _lifespan(app: FastAPI):
    scheduler = create_feedback_scheduler()
    app.state.feedback_scheduler = scheduler
    if scheduler:
        await scheduler.start()
    try:
        yield
    finally:
        scheduler = getattr(app.state, "feedback_scheduler", None)
        if scheduler:
            await scheduler.stop()


app = FastAPI(
    title="SIGNAL API",
    description="Brand intake, trend signals, campaign generation, content production, and self-improving feedback loops",
    version="0.2.0",
    lifespan=_lifespan,
)

_CORS_ORIGINS_RAW = os.getenv("CORS_ALLOW_ORIGINS", "*")
_CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]
_ALLOW_ALL_ORIGINS = "*" in _CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _ALLOW_ALL_ORIGINS else _CORS_ORIGINS,
    allow_credentials=not _ALLOW_ALL_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return 500 with detail for debugging."""
    from fastapi import HTTPException
    if isinstance(exc, HTTPException):
        raise exc  # Let FastAPI handle HTTP exceptions (404, 422, etc.)
    logging.exception("Unhandled exception: %s", exc)
    include_detail = settings.ENVIRONMENT.lower() in {"development", "dev", "local", "test"}
    return JSONResponse(
        status_code=500,
        content=(
            {"detail": str(exc), "type": type(exc).__name__}
            if include_detail
            else {"detail": "Internal server error"}
        ),
    )

# Existing company router
app.include_router(company.router)

# New feature routers
app.include_router(signals_router.router)
app.include_router(campaigns_router.router)
app.include_router(content_router.router)
app.include_router(feedback_router.router)
app.include_router(jobs_router.router)

# Serve generated media
MEDIA_DIR = Path(os.getenv("MEDIA_OUTPUT_DIR", "./data/generated_media"))
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")



@app.get("/")
async def root():
    return {"service": "SIGNAL", "version": "0.2.0", "docs": "/docs"}


@app.get("/health")
async def health():
    """Basic health check — returns 200 when the service is running."""
    return {"status": "ok"}
