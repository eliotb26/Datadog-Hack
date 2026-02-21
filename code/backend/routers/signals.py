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

def _get_demo_trend_signals(company: "CompanyProfile") -> list:
    """Return minimal demo TrendSignal list when live providers are unavailable."""
    from backend.models.signal import TrendSignal

    base_signals = [
        ("Will AI tools transform marketing by 2026?", "tech", 0.62, 0.08, 125_000),
        ("B2B SaaS adoption accelerating in enterprise", "tech", 0.71, 0.12, 85_000),
        ("Content marketing ROI becoming measurable at scale", "marketing", 0.58, 0.05, 45_000),
    ]
    out = []
    for title, category, prob, momentum, vol in base_signals:
        sig = TrendSignal(
            id=str(uuid.uuid4()),
            polymarket_market_id=f"demo-{uuid.uuid4().hex[:8]}",
            title=title,
            category=category,
            probability=prob,
            probability_momentum=momentum,
            volume=vol,
            volume_velocity=0.15,
            relevance_scores={company.id: 0.75},
            confidence_score=0.8,
        )
        out.append(sig)
    return out


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
        "confidence_score": float(row.get("confidence_score") or 0),
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
    volume_threshold: float = 10000.0


# ---------------------------------------------------------------------------
# Async worker: run Agent 2 and persist returned signals
# ---------------------------------------------------------------------------

async def _refresh_signals_worker(
    company_id: Optional[str],
    top_n: int,
    volume_threshold: float,
) -> dict:
    from backend.models.company import CompanyProfile
    from backend.models.signal import TrendSignal
    from backend.agents.trend_intel import run_trend_agent

    # Load company profile
    if company_id:
        row = await db_module.get_company_by_id(company_id)
    else:
        row = await db_module.get_latest_company_row()

    if row:
        company = CompanyProfile.from_db_row(row)
    else:
        # Keep trending refresh usable even before onboarding.
        company = CompanyProfile(
            id="demo-company",
            name="Demo Company",
            industry="general",
        )
        log.info("signals_refresh_using_demo_company_profile")

    # Run Agent 2
    try:
        signals = await run_trend_agent(
            company=company,
            top_n=top_n,
            volume_threshold=volume_threshold,
        )
    except Exception as exc:
        log.warning("trend_agent_failed_using_fallback: %s", exc)
        signals = []

    if not signals:
        existing_rows = await db_module.list_signals(limit=max(5, top_n))
        loaded: list[TrendSignal] = []
        for sr in existing_rows:
            rel = sr.get("relevance_scores", "{}")
            if isinstance(rel, str):
                try:
                    rel = json.loads(rel)
                except Exception:
                    rel = {}
            if not rel and company.id:
                rel = {company.id: 0.7}
            loaded.append(
                TrendSignal(
                    id=sr["id"],
                    polymarket_market_id=sr.get("polymarket_market_id", ""),
                    title=sr.get("title", ""),
                    category=sr.get("category"),
                    probability=float(sr.get("probability") or 0.5),
                    probability_momentum=float(sr.get("probability_momentum") or 0),
                    volume=float(sr.get("volume") or 0),
                    volume_velocity=float(sr.get("volume_velocity") or 0),
                    relevance_scores=rel,
                    confidence_score=float(sr.get("confidence_score") or 0),
                )
            )
        signals = loaded

    if not signals:
        signals = _get_demo_trend_signals(company)[:top_n]

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
            "confidence_score": sig.confidence_score,
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
        run_job(
            job.job_id,
            _refresh_signals_worker(
                req.company_id,
                req.top_n,
                req.volume_threshold,
            ),
        )
    )
    return {"job_id": job.job_id, "status": job.status}
