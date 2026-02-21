"""Campaigns router — /api/campaigns

POST /api/campaigns/generate        — async job: Agent 2 (optional) → Agent 3 → Agent 4
GET  /api/campaigns                 — list campaigns (company_id, status filters)
GET  /api/campaigns/{id}            — campaign detail + metrics
POST /api/campaigns/{id}/approve    — mark campaign approved
POST /api/campaigns/{id}/metrics    — submit performance data (triggers Loop 1 feedback)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import backend.database as db_module
from backend.jobs import JobType, create_job, run_job

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_demo_trend_signals(company: "CompanyProfile") -> list:
    """Return minimal demo TrendSignal list when Polymarket/trend agent returns empty."""
    from backend.models.signal import TrendSignal
    import uuid as _uuid

    base_signals = [
        ("Will AI tools transform marketing by 2026?", "tech", 0.62, 0.08, 125_000),
        ("B2B SaaS adoption accelerating in enterprise", "tech", 0.71, 0.12, 85_000),
        ("Content marketing ROI becoming measurable at scale", "marketing", 0.58, 0.05, 45_000),
    ]
    out = []
    for title, category, prob, momentum, vol in base_signals:
        sig = TrendSignal(
            id=str(_uuid.uuid4()),
            polymarket_market_id=f"demo-{_uuid.uuid4().hex[:8]}",
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
    return {
        "id": row["id"],
        "company_id": row.get("company_id"),
        "trend_signal_id": row.get("trend_signal_id"),
        "headline": row.get("headline", ""),
        "body_copy": row.get("body_copy", ""),
        "visual_direction": row.get("visual_direction", ""),
        "visual_asset_url": row.get("visual_asset_url"),
        "confidence_score": float(row.get("confidence_score") or 0),
        "channel_recommendation": row.get("channel_recommendation", ""),
        "channel_reasoning": row.get("channel_reasoning", ""),
        "safety_score": row.get("safety_score"),
        "safety_passed": bool(row.get("safety_passed", 1)),
        "status": row.get("status", "draft"),
        "created_at": row.get("created_at"),
    }


async def _load_feedback_prompt_weights(company: "CompanyProfile") -> Dict[str, Any]:
    """Merge Loop 1 prompt weights with Loop 2 shared patterns."""
    try:
        weights = await db_module.get_prompt_weights(company.id, agent_name="campaign_gen")
    except Exception as e:
        log.warning("get_prompt_weights_failed: %s", e)
        weights = {}

    try:
        patterns = await db_module.get_shared_patterns(
            industry=company.industry,
            min_confidence=0.55,
            limit=5,
        )
    except Exception as e:
        log.warning("get_shared_patterns_failed: %s", e)
        patterns = []

    if not patterns:
        return weights

    style_hints: List[str] = []
    for pattern in patterns:
        desc = str(pattern.get("description", "")).strip()
        effect = pattern.get("effect") or {}
        rec_channel = str(effect.get("recommended_channel", "")).strip()
        if rec_channel and desc:
            style_hints.append(f"{desc} Prefer channel: {rec_channel}.")
        elif desc:
            style_hints.append(desc)

    if style_hints:
        existing = str(weights.get("learned_preferences", "")).strip()
        merged = "\n".join(style_hints)
        weights["learned_preferences"] = f"{existing}\n{merged}".strip() if existing else merged

    return weights


# ---------------------------------------------------------------------------
# Campaign generation job
# ---------------------------------------------------------------------------

class GenerateCampaignsRequest(BaseModel):
    company_id: Optional[str] = None
    signal_ids: Optional[List[str]] = Field(
        default=None,
        description="If omitted, Agent 2 runs first to surface fresh signals",
    )
    n_concepts: int = Field(default=3, ge=1, le=5)


async def _generate_campaigns_worker(
    company_id: Optional[str],
    signal_ids: Optional[List[str]],
    n_concepts: int,
) -> dict:
    from backend.models.company import CompanyProfile
    from backend.models.signal import TrendSignal
    from backend.agents.campaign_gen import run_campaign_agent
    from backend.agents.distribution import DistributionRoutingAgent

    # 1. Load company
    if company_id:
        row = await db_module.get_company_by_id(company_id)
    else:
        row = await db_module.get_latest_company_row()

    if not row:
        raise ValueError("No company profile found. Please complete onboarding first.")

    company = CompanyProfile.from_db_row(row)

    # 2. Load or refresh signals
    if signal_ids:
        signal_rows = [
            r for sid in signal_ids
            if (r := await db_module.get_signal_by_id(sid)) is not None
        ]
        import json as _json
        signals = []
        for sr in signal_rows:
            rel = sr.get("relevance_scores", "{}")
            if isinstance(rel, str):
                try:
                    rel = _json.loads(rel)
                except Exception:
                    rel = {}
            signals.append(TrendSignal(
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
            ))
    else:
        from backend.agents.trend_intel import run_trend_agent
        import json as _json
        try:
            signals = await run_trend_agent(company=company, top_n=5)
        except Exception as e:
            log.warning("trend_agent_failed_using_fallback: %s", e)
            signals = []

        # Fallback: use existing signals from DB or create demo signals when Polymarket returns empty
        if not signals:
            existing = await db_module.list_signals(limit=5)
            if existing:
                for sr in existing:
                    rel = sr.get("relevance_scores", "{}")
                    if isinstance(rel, str):
                        try:
                            rel = _json.loads(rel)
                        except Exception:
                            rel = {}
                    if not rel and company.id:
                        rel = {company.id: 0.7}
                    signals.append(TrendSignal(
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
                    ))
            else:
                # Create minimal demo signals so campaign gen can proceed
                _demo_signals = _get_demo_trend_signals(company)
                signals = _demo_signals

        # persist fresh signals
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
                "relevance_scores": _json.dumps(sig.relevance_scores),
                "surfaced_at": sig.surfaced_at.isoformat(),
                "expires_at": sig.expires_at.isoformat() if sig.expires_at else None,
            }
            await db_module.insert_signal(sig_row)

    if not signals:
        raise ValueError("No trend signals available. Try refreshing signals first.")

    # 3. Run Agent 3 — Campaign Generation
    prompt_weights = await _load_feedback_prompt_weights(company)
    gen_response = await run_campaign_agent(
        company=company,
        signals=signals,
        prompt_weights=prompt_weights,
        n_concepts=n_concepts,
        persist=True,
    )

    concepts = gen_response.concepts

    # 4. Run Agent 4 — Distribution Routing
    dist_agent = DistributionRoutingAgent()
    company_dict = {
        "id": company.id,
        "name": company.name,
        "industry": company.industry,
        "target_audience": company.target_audience or "",
        "tone_of_voice": company.tone_of_voice or "",
        "campaign_goals": company.campaign_goals or "",
    }
    distribution_plans = await dist_agent.route_campaigns(concepts, company_dict)

    # Merge distribution channel back onto campaign status if it differs
    from backend.models.campaign import Channel
    plan_map = {p.campaign_id: p for p in distribution_plans}
    for concept in concepts:
        plan = plan_map.get(concept.id)
        if plan and plan.recommended_channel != concept.channel_recommendation.value:
            try:
                concept.channel_recommendation = Channel(
                    plan.recommended_channel.lower()
                    if isinstance(plan.recommended_channel, str)
                    else plan.recommended_channel
                )
            except ValueError:
                pass  # keep existing if invalid channel
            await db_module.update_campaign_status(concept.id, concept.status)

    return {
        "company_id": company.id,
        "campaigns": [c.to_dict() for c in concepts],
        "distribution_plans": [p.to_db_row() for p in distribution_plans],
        "signals_used": [s.to_dict() for s in signals],
    }


@router.post("/generate", status_code=202)
async def generate_campaigns(req: GenerateCampaignsRequest):
    """Submit async campaign generation job (Agent 2 → Agent 3 → Agent 4).

    Returns job_id — poll GET /api/jobs/{job_id} for completion.
    """
    job = create_job(JobType.CAMPAIGN_GENERATE)
    asyncio.create_task(
        run_job(
            job.job_id,
            _generate_campaigns_worker(req.company_id, req.signal_ids, req.n_concepts),
        )
    )
    return {"job_id": job.job_id, "status": job.status}


# ---------------------------------------------------------------------------
# Resource endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_campaigns(
    company_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    """List campaigns with optional filters."""
    rows = await db_module.list_campaigns(
        company_id=company_id, status=status, limit=limit
    )
    return [_row_to_api(r) for r in rows]


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Return campaign detail including performance metrics."""
    row = await db_module.get_campaign_by_id(campaign_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id!r} not found")
    result = _row_to_api(row)
    result["metrics"] = await db_module.get_campaign_metrics(campaign_id)
    return result


@router.post("/{campaign_id}/approve")
async def approve_campaign(campaign_id: str):
    """Mark a campaign as approved."""
    row = await db_module.get_campaign_by_id(campaign_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id!r} not found")
    await db_module.update_campaign_status(campaign_id, "approved")
    return {"campaign_id": campaign_id, "status": "approved"}


# ---------------------------------------------------------------------------
# Metrics submission
# ---------------------------------------------------------------------------

class MetricsRequest(BaseModel):
    channel: str
    impressions: int = 0
    clicks: int = 0
    engagement_rate: float = 0.0
    sentiment_score: Optional[float] = None


@router.post("/{campaign_id}/metrics")
async def submit_metrics(campaign_id: str, req: MetricsRequest):
    """Submit performance metrics for a campaign (used by Loop 1 feedback)."""
    row = await db_module.get_campaign_by_id(campaign_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id!r} not found")

    metric_id = str(uuid.uuid4())
    await db_module.insert_campaign_metrics({
        "id": metric_id,
        "campaign_id": campaign_id,
        "channel": req.channel,
        "impressions": req.impressions,
        "clicks": req.clicks,
        "engagement_rate": req.engagement_rate,
        "sentiment_score": req.sentiment_score,
        "measured_at": datetime.utcnow().isoformat(),
    })
    return {"metric_id": metric_id, "campaign_id": campaign_id, "status": "recorded"}
