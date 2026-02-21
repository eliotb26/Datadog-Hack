"""Signals router — /api/signals

GET  /api/signals           — list persisted trend signals
GET  /api/signals/{id}      — single signal detail
POST /api/signals/refresh   — async job: run Agent 2 to poll Polymarket and surface fresh signals
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import backend.database as db_module
from backend.jobs import JobType, create_job, run_job

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signals", tags=["signals"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_api(row: dict) -> dict:
    """Convert a DB row into an API-friendly dict the frontend can consume."""
    relevance_raw = row.get("relevance_scores") or "{}"
    if isinstance(relevance_raw, str):
        try:
            relevance = json.loads(relevance_raw)
        except Exception:
            relevance = {}
    else:
        relevance = relevance_raw

    return {
        "id": row["id"],
        "polymarket_market_id": row.get("polymarket_market_id", ""),
        "title": row.get("title", ""),
        "category": row.get("category") or "general",
        "probability": float(row.get("probability") or 0),
        "probability_pct": round(float(row.get("probability") or 0) * 100, 1),
        "probability_momentum": float(row.get("probability_momentum") or 0),
        "volume": float(row.get("volume") or 0),
        "volume_velocity": float(row.get("volume_velocity") or 0),
        "relevance_scores": relevance,
        "surfaced_at": row.get("surfaced_at"),
        "expires_at": row.get("expires_at"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_signals(
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    """Return all persisted trend signals, newest first."""
    rows = await db_module.list_signals(
        category=category,
        limit=limit,
    )
    return [_row_to_api(r) for r in rows]


@router.get("/{signal_id}")
async def get_signal(signal_id: str):
    """Return a single trend signal by ID."""
    row = await db_module.get_signal_by_id(signal_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id!r} not found")
    return _row_to_api(row)


# ---------------------------------------------------------------------------
# Signal refresh request body
# ---------------------------------------------------------------------------

class SignalRefreshRequest(BaseModel):
    company_id: Optional[str] = None
    top_n: int = 5


# ---------------------------------------------------------------------------
# Async worker: run Agent 2 and persist returned signals
# ---------------------------------------------------------------------------

async def _refresh_signals_worker(company_id: Optional[str], top_n: int) -> dict:
    from backend.models.company import CompanyProfile
    from backend.agents.trend_intel import run_trend_agent

    # Load company profile
    if company_id:
        row = await db_module.get_company_by_id(company_id)
    else:
        row = await db_module.get_latest_company_row()

    if not row:
        raise ValueError("No company profile found. Please complete onboarding first.")

    company = CompanyProfile.from_db_row(row)

    # Run Agent 2
    signals = await run_trend_agent(company=company, top_n=top_n)

    # Persist returned signals to DB
    persisted = []
    for sig in signals:
        sig_row = {
            "id": sig.id,
            "polymarket_market_id": sig.polymarket_market_id,
            "title": sig.title,
            "category": sig.category,
            "probability": sig.probability,
            "probability_momentum": sig.probability_momentum,
            "volume": sig.volume,
            "volume_velocity": sig.volume_velocity,
            "relevance_scores": json.dumps(sig.relevance_scores),
            "surfaced_at": sig.surfaced_at.isoformat(),
            "expires_at": sig.expires_at.isoformat() if sig.expires_at else None,
        }
        await db_module.insert_signal(sig_row)
        persisted.append(sig.to_dict())

    return {"signals_surfaced": len(persisted), "signals": persisted}


@router.post("/refresh", status_code=202)
async def refresh_signals(req: SignalRefreshRequest):
    """Submit an async job that runs Agent 2 and persists fresh Polymarket signals.

    Returns job_id — poll GET /api/jobs/{job_id} for completion.
    """
    job = create_job(JobType.SIGNAL_REFRESH)
    asyncio.create_task(
        run_job(job.job_id, _refresh_signals_worker(req.company_id, req.top_n))
    )
    return {"job_id": job.job_id, "status": job.status}
