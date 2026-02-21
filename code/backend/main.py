"""
SIGNAL Backend — FastAPI app entry point (company profile + brand intake).
Run from repo root with PYTHONPATH=code:  uvicorn backend.main:app --reload --port 8000
Or from code/backend with PYTHONPATH=code:  python -m uvicorn backend.main:app --reload --port 8000
"""
import logging
import os
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

app = FastAPI(
    title="SIGNAL API",
    description="Brand intake, trend signals, campaign generation, content production, and self-improving feedback loops",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
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

# Lightdash router (optional — uncomment when lightdash integration is configured):
# from backend.routers import lightdash; app.include_router(lightdash.router)


@app.get("/")
async def root():
    return {"service": "SIGNAL", "version": "0.2.0", "docs": "/docs"}


@app.on_event("startup")
async def _startup_scheduler() -> None:
    scheduler = create_feedback_scheduler()
    app.state.feedback_scheduler = scheduler
    if scheduler:
        await scheduler.start()


@app.on_event("shutdown")
async def _shutdown_scheduler() -> None:
    scheduler = getattr(app.state, "feedback_scheduler", None)
    if scheduler:
        await scheduler.stop()


@app.get("/health")
async def health():
    """Basic health check — returns 200 when the service is running."""
    return {"status": "ok"}
