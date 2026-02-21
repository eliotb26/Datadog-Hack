"""Content router — /api/content

POST /api/content/strategies/generate    — async job: Agent 6 (content strategy)
GET  /api/content/strategies             — list strategies (campaign_id, company_id filters)
GET  /api/content/strategies/{id}        — single strategy detail
POST /api/content/pieces/generate        — async job: Agent 7 (content production)
GET  /api/content/pieces                 — list pieces (strategy_id, campaign_id, company_id)
GET  /api/content/pieces/{id}            — single content piece
PATCH /api/content/pieces/{id}/status   — update piece status (draft/review/approved/published)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import backend.database as db_module
from backend.jobs import JobType, create_job, run_job

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/content", tags=["content"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strategy_row_to_api(row: dict) -> dict:
    outline = row.get("structure_outline", "[]")
    if isinstance(outline, str):
        try:
            outline = json.loads(outline)
        except Exception:
            outline = []
    return {
        "id": row["id"],
        "campaign_id": row.get("campaign_id"),
        "company_id": row.get("company_id"),
        "content_type": row.get("content_type"),
        "reasoning": row.get("reasoning", ""),
        "target_length": row.get("target_length", ""),
        "tone_direction": row.get("tone_direction", ""),
        "structure_outline": outline,
        "priority_score": float(row.get("priority_score") or 0.5),
        "visual_needed": bool(row.get("visual_needed", 0)),
        "created_at": row.get("created_at"),
    }


def _piece_row_to_api(row: dict) -> dict:
    return {
        "id": row["id"],
        "strategy_id": row.get("strategy_id"),
        "campaign_id": row.get("campaign_id"),
        "company_id": row.get("company_id"),
        "content_type": row.get("content_type"),
        "title": row.get("title", ""),
        "body": row.get("body", ""),
        "summary": row.get("summary", ""),
        "word_count": int(row.get("word_count") or 0),
        "visual_prompt": row.get("visual_prompt"),
        "visual_asset_url": row.get("visual_asset_url"),
        "quality_score": float(row.get("quality_score") or 0),
        "brand_alignment": float(row.get("brand_alignment") or 0),
        "status": row.get("status", "draft"),
        "created_at": row.get("created_at"),
    }


# ---------------------------------------------------------------------------
# Content strategy generation job (Agent 6)
# ---------------------------------------------------------------------------

class GenerateStrategyRequest(BaseModel):
    campaign_id: str


async def _generate_strategy_worker(campaign_id: str) -> dict:
    from backend.agents.content_strategy import run_content_strategy_agent
    from backend.models.company import CompanyProfile

    # Load campaign
    camp_row = await db_module.get_campaign_by_id(campaign_id)
    if not camp_row:
        raise ValueError(f"Campaign {campaign_id!r} not found")

    # Load company
    company_id = camp_row.get("company_id")
    company_row = await db_module.get_company_by_id(company_id) if company_id else None
    if not company_row:
        company_row = await db_module.get_latest_company_row()
    if not company_row:
        raise ValueError("No company profile found")

    company = CompanyProfile.from_db_row(company_row)

    response = await run_content_strategy_agent(
        campaign_id=campaign_id,
        company_id=company.id,
        headline=camp_row.get("headline", ""),
        body_copy=camp_row.get("body_copy", ""),
        channel_recommendation=camp_row.get("channel_recommendation", ""),
        company_name=company.name,
        industry=company.industry,
        tone=company.tone_of_voice or "",
        audience=company.target_audience or "",
        goals=company.campaign_goals or "",
        persist=True,
    )

    return {
        "campaign_id": campaign_id,
        "strategies": [s.to_dict() for s in response.strategies],
        "success": response.success,
    }


@router.post("/strategies/generate", status_code=202)
async def generate_strategy(req: GenerateStrategyRequest):
    """Submit async job: run Agent 6 to choose content formats for a campaign.

    Returns job_id — poll GET /api/jobs/{job_id} for completion.
    """
    job = create_job(JobType.CONTENT_STRATEGY_GENERATE)
    asyncio.create_task(
        run_job(job.job_id, _generate_strategy_worker(req.campaign_id))
    )
    return {"job_id": job.job_id, "status": job.status}


@router.get("/strategies")
async def list_strategies(
    campaign_id: Optional[str] = Query(default=None),
    company_id: Optional[str] = Query(default=None),
):
    """List content strategies with optional filters."""
    rows = await db_module.list_content_strategies(
        campaign_id=campaign_id, company_id=company_id
    )
    return [_strategy_row_to_api(r) for r in rows]


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Return a single content strategy."""
    row = await db_module.get_content_strategy_by_id(strategy_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id!r} not found")
    return _strategy_row_to_api(row)


# ---------------------------------------------------------------------------
# Content piece generation job (Agent 7)
# ---------------------------------------------------------------------------

class GeneratePieceRequest(BaseModel):
    strategy_id: str


async def _generate_piece_worker(strategy_id: str) -> dict:
    from backend.agents.content_production import run_content_production_agent
    from backend.models.content import ContentStrategy, ContentType
    from backend.models.company import CompanyProfile

    # Load strategy
    strat_row = await db_module.get_content_strategy_by_id(strategy_id)
    if not strat_row:
        raise ValueError(f"Strategy {strategy_id!r} not found")

    strategy = ContentStrategy.from_db_row(strat_row)

    # Load campaign
    camp_row = await db_module.get_campaign_by_id(strategy.campaign_id)
    if not camp_row:
        raise ValueError(f"Campaign {strategy.campaign_id!r} not found")

    # Load company
    company_id = camp_row.get("company_id")
    company_row = await db_module.get_company_by_id(company_id) if company_id else None
    if not company_row:
        company_row = await db_module.get_latest_company_row()
    if not company_row:
        raise ValueError("No company profile found")

    company = CompanyProfile.from_db_row(company_row)

    response = await run_content_production_agent(
        strategy=strategy,
        campaign_headline=camp_row.get("headline", ""),
        campaign_body_copy=camp_row.get("body_copy", ""),
        company_name=company.name,
        tone=company.tone_of_voice or "",
        audience=company.target_audience or "",
        goals=company.campaign_goals or "",
        persist=True,
    )

    return {
        "strategy_id": strategy_id,
        "pieces": [p.to_dict() for p in response.pieces],
        "success": response.success,
    }


@router.post("/pieces/generate", status_code=202)
async def generate_piece(req: GeneratePieceRequest):
    """Submit async job: run Agent 7 to produce full content from a strategy.

    Returns job_id — poll GET /api/jobs/{job_id} for completion.
    """
    job = create_job(JobType.CONTENT_PIECE_GENERATE)
    asyncio.create_task(
        run_job(job.job_id, _generate_piece_worker(req.strategy_id))
    )
    return {"job_id": job.job_id, "status": job.status}


@router.get("/pieces")
async def list_pieces(
    strategy_id: Optional[str] = Query(default=None),
    campaign_id: Optional[str] = Query(default=None),
    company_id: Optional[str] = Query(default=None),
):
    """List content pieces with optional filters."""
    rows = await db_module.list_content_pieces(
        strategy_id=strategy_id,
        campaign_id=campaign_id,
        company_id=company_id,
    )
    return [_piece_row_to_api(r) for r in rows]


@router.get("/pieces/{piece_id}")
async def get_piece(piece_id: str):
    """Return a single content piece."""
    row = await db_module.get_content_piece_by_id(piece_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Content piece {piece_id!r} not found")
    return _piece_row_to_api(row)


class StatusUpdateRequest(BaseModel):
    status: str  # draft | review | approved | published


@router.patch("/pieces/{piece_id}/status")
async def update_piece_status(piece_id: str, req: StatusUpdateRequest):
    """Update the review/publish status of a content piece."""
    allowed = {"draft", "review", "approved", "published"}
    if req.status not in allowed:
        raise HTTPException(
            status_code=422, detail=f"status must be one of {sorted(allowed)}"
        )
    row = await db_module.get_content_piece_by_id(piece_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Content piece {piece_id!r} not found")
    await db_module.update_content_piece_status(piece_id, req.status)
    return {"piece_id": piece_id, "status": req.status}
