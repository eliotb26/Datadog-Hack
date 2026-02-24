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
import os
from types import SimpleNamespace
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import backend.database as db_module
from backend.jobs import JobType, create_job, run_job

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/content", tags=["content"])
_CONTENT_STRATEGY_TIMEOUT_S = int(os.getenv("CONTENT_STRATEGY_TIMEOUT_S", "45"))
_CONTENT_PRODUCTION_TIMEOUT_S = int(os.getenv("CONTENT_PRODUCTION_TIMEOUT_S", "45"))


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


def _fallback_strategies(
    campaign_id: str,
    company_id: str,
    channel_recommendation: str,
    error_reason: str | None = None,
) -> list["ContentStrategy"]:
    from backend.models.content import ContentStrategy, ContentType

    channel = (channel_recommendation or "").lower()
    if channel == "twitter":
        content_type = ContentType.TWEET_THREAD
        target_length = "5-tweet thread"
    elif channel == "instagram":
        content_type = ContentType.INSTAGRAM_CAROUSEL
        target_length = "6-slide carousel"
    elif channel == "newsletter":
        content_type = ContentType.NEWSLETTER
        target_length = "600-word newsletter"
    else:
        content_type = ContentType.LINKEDIN_ARTICLE
        target_length = "900-word article"

    reason_suffix = f" Root cause: {error_reason}" if error_reason else ""
    return [
        ContentStrategy(
            campaign_id=campaign_id,
            company_id=company_id,
            content_type=content_type,
            reasoning=(
                "Fallback strategy generated because live strategy model was unavailable."
                f"{reason_suffix}"
            ),
            target_length=target_length,
            tone_direction="Clear, practical, and brand-aligned.",
            structure_outline=["Hook", "Key insight", "Actionable guidance", "Call to action"],
            priority_score=0.6,
            visual_needed=content_type in {ContentType.INSTAGRAM_CAROUSEL, ContentType.INFOGRAPHIC, ContentType.VIDEO_SCRIPT},
        )
    ]


async def _persist_fallback_strategies(strategies: list["ContentStrategy"]) -> None:
    await db_module.init_db(db_module.DB_PATH)
    async with aiosqlite.connect(db_module.DB_PATH) as db:
        for strategy in strategies:
            await db.execute(
                """
                INSERT OR REPLACE INTO content_strategies
                    (id, campaign_id, company_id, content_type, reasoning,
                     target_length, tone_direction, structure_outline,
                     priority_score, visual_needed, created_at)
                VALUES
                    (:id, :campaign_id, :company_id, :content_type, :reasoning,
                     :target_length, :tone_direction, :structure_outline,
                     :priority_score, :visual_needed, :created_at)
                """,
                strategy.to_db_row(),
            )
        await db.commit()


def _fallback_pieces(
    strategy: "ContentStrategy",
    campaign_headline: str,
    error_reason: str | None = None,
) -> list["ContentPiece"]:
    from backend.models.content import ContentPiece

    reason_suffix = f" Root cause: {error_reason}" if error_reason else ""
    body = (
        f"{campaign_headline}\n\n"
        "1) Why this matters right now.\n"
        "2) A practical perspective tied to the campaign objective.\n"
        "3) A clear next step for the audience.\n\n"
        "CTA: Reply or message us to apply this approach in your own workflow."
    )
    return [
        ContentPiece(
            strategy_id=strategy.id,
            campaign_id=strategy.campaign_id,
            company_id=strategy.company_id,
            content_type=strategy.content_type,
            title=campaign_headline[:100] or "Campaign Content",
            body=body,
            summary=(
                "Fallback content piece generated because live production model was unavailable."
                f"{reason_suffix}"
            ),
            word_count=len(body.split()),
            quality_score=0.55,
            brand_alignment=0.6,
        )
    ]


async def _persist_fallback_pieces(pieces: list["ContentPiece"]) -> None:
    await db_module.init_db(db_module.DB_PATH)
    async with aiosqlite.connect(db_module.DB_PATH) as db:
        for piece in pieces:
            await db.execute(
                """
                INSERT OR REPLACE INTO content_pieces
                    (id, strategy_id, campaign_id, company_id, content_type,
                     title, body, summary, word_count, visual_prompt,
                     visual_asset_url, quality_score, brand_alignment,
                     status, created_at)
                VALUES
                    (:id, :strategy_id, :campaign_id, :company_id, :content_type,
                     :title, :body, :summary, :word_count, :visual_prompt,
                     :visual_asset_url, :quality_score, :brand_alignment,
                     :status, :created_at)
                """,
                piece.to_db_row(),
            )
        await db.commit()


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

    fallback_used = False
    fallback_reason: str | None = None
    try:
        response = await asyncio.wait_for(
            run_content_strategy_agent(
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
            ),
            timeout=_CONTENT_STRATEGY_TIMEOUT_S,
        )
    except Exception as e:
        fallback_used = True
        fallback_reason = str(e)
        log.warning("content_strategy_agent_failed_using_fallback: %s", e)
        fallback = _fallback_strategies(
            campaign_id=campaign_id,
            company_id=company.id,
            channel_recommendation=camp_row.get("channel_recommendation", ""),
            error_reason=fallback_reason,
        )
        await _persist_fallback_strategies(fallback)
        response = SimpleNamespace(strategies=fallback, success=True)

    if not response.strategies:
        fallback_used = True
        fallback_reason = fallback_reason or "Live strategy response returned no strategies."
        fallback = _fallback_strategies(
            campaign_id=campaign_id,
            company_id=company.id,
            channel_recommendation=camp_row.get("channel_recommendation", ""),
            error_reason=fallback_reason,
        )
        await _persist_fallback_strategies(fallback)
        response = SimpleNamespace(strategies=fallback, success=True)

    return {
        "campaign_id": campaign_id,
        "strategies": [s.to_dict() for s in response.strategies],
        "success": response.success,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
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

    fallback_used = False
    fallback_reason: str | None = None
    campaign_headline = camp_row.get("headline", "")
    try:
        response = await asyncio.wait_for(
            run_content_production_agent(
                strategy=strategy,
                campaign_headline=campaign_headline,
                campaign_body_copy=camp_row.get("body_copy", ""),
                company_name=company.name,
                tone=company.tone_of_voice or "",
                audience=company.target_audience or "",
                goals=company.campaign_goals or "",
                persist=True,
            ),
            timeout=_CONTENT_PRODUCTION_TIMEOUT_S,
        )
    except Exception as e:
        fallback_used = True
        fallback_reason = str(e)
        log.warning("content_production_agent_failed_using_fallback: %s", e)
        fallback = _fallback_pieces(strategy, campaign_headline, error_reason=fallback_reason)
        await _persist_fallback_pieces(fallback)
        response = SimpleNamespace(pieces=fallback, success=True)

    if not response.pieces:
        fallback_used = True
        fallback_reason = fallback_reason or "Live production response returned no content pieces."
        fallback = _fallback_pieces(strategy, campaign_headline, error_reason=fallback_reason)
        await _persist_fallback_pieces(fallback)
        response = SimpleNamespace(pieces=fallback, success=True)

    return {
        "strategy_id": strategy_id,
        "pieces": [p.to_dict() for p in response.pieces],
        "success": response.success,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
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
