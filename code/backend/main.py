"""
SIGNAL — FastAPI application entry point.
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Allow bare imports (e.g. `from config import settings`) throughout the package
# when the server is launched as `uvicorn backend.main:app` from the `code/` dir.
sys.path.insert(0, str(Path(__file__).parent))

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from integrations.logging_setup import configure_logging
from routers.lightdash import router as lightdash_router

configure_logging(settings.LOG_LEVEL)
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("signal_startup", environment=settings.ENVIRONMENT)
    await init_db()
    log.info("database_ready")
    yield
    log.info("signal_shutdown")


app = FastAPI(
    title="SIGNAL",
    description="AI-powered trend-driven campaign generation platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lightdash_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.DD_SERVICE, "env": settings.ENVIRONMENT}
