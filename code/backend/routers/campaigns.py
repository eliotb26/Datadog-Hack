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
import os
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

import backend.database as db_module
from backend.jobs import JobType, create_job, run_job, update_progress

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])
_TREND_AGENT_TIMEOUT_S = 12
_CAMPAIGN_AGENT_TIMEOUT_S = int(os.getenv("CAMPAIGN_AGENT_TIMEOUT_S", "45"))
_DISTRIBUTION_AGENT_TIMEOUT_S = int(os.getenv("DISTRIBUTION_AGENT_TIMEOUT_S", "30"))


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


def _fallback_campaign_concepts(
    company: "CompanyProfile",
    signals: list["TrendSignal"],
    n_concepts: int,
) -> list["CampaignConcept"]:
    from backend.models.campaign import CampaignConcept, Channel

    safe_signals = signals or _get_demo_trend_signals(company)
    concepts: list[CampaignConcept] = []
    for i in range(max(1, n_concepts)):
        signal = safe_signals[i % len(safe_signals)]
        if company.industry.lower() in {"technology", "saas", "marketing"}:
            channel = Channel.LINKEDIN
        else:
            channel = Channel.NEWSLETTER
        concepts.append(
            CampaignConcept(
                company_id=company.id,
                trend_signal_id=signal.id,
                headline=f"{company.name}: {signal.title[:72]}",
                body_copy=(
                    f"{company.name} can turn this trend into practical value. "
                    f"Publish a concise perspective on '{signal.title}' with one clear takeaway, "
                    "one actionable next step, and a direct call to engage."
                ),
                visual_direction="Bold headline card, clean data overlay, brand color accents.",
                confidence_score=0.62,
                channel_recommendation=channel,
                channel_reasoning="Chosen as a reliable default channel for high-intent audiences.",
            )
        )
    return concepts


async def _persist_fallback_campaigns(concepts: list["CampaignConcept"]) -> None:
    await db_module.init_db(db_module.DB_PATH)
    async with aiosqlite.connect(db_module.DB_PATH) as db:
        for concept in concepts:
            await db.execute(
                """
                INSERT OR REPLACE INTO campaigns
                    (id, company_id, trend_signal_id, headline, body_copy,
                     visual_direction, visual_asset_url, confidence_score,
                     channel_recommendation, channel_reasoning,
                     safety_score, safety_passed, status, created_at)
                VALUES
                    (:id, :company_id, :trend_signal_id, :headline, :body_copy,
                     :visual_direction, :visual_asset_url, :confidence_score,
                     :channel_recommendation, :channel_reasoning,
                     :safety_score, :safety_passed, :status, :created_at)
                """,
                concept.to_db_row(),
            )
        await db.commit()


def _fallback_distribution_plans(
    company: "CompanyProfile",
    concepts: list["CampaignConcept"],
) -> list["DistributionPlan"]:
    from backend.models.campaign import ChannelScore, DistributionPlan

    plans: list[DistributionPlan] = []
    for concept in concepts:
        rec = concept.channel_recommendation.value
        plans.append(
            DistributionPlan(
                campaign_id=concept.id,
                company_id=company.id,
                recommended_channel=rec,
                channel_scores=[
                    ChannelScore(
                        channel=rec,
                        fit_score=0.74,
                        length_fit=0.72,
                        visual_fit=0.70,
                        audience_fit=0.78,
                        reasoning="Default routing fallback selected for reliability.",
                    )
                ],
                posting_time="Tuesday 9-11 AM local time",
                format_adaptation="Lead with a one-sentence hook, then 3 concise proof points and a CTA.",
                character_count_target=900,
                visual_required=False,
                reasoning="Fallback routing used because live distribution scoring was unavailable.",
                confidence=0.6,
            )
        )
    return plans


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
    job_id: str,
    company_id: Optional[str],
    signal_ids: Optional[List[str]],
    n_concepts: int,
) -> dict:
    from backend.models.company import CompanyProfile
    from backend.models.signal import TrendSignal
    from backend.agents.campaign_gen import run_campaign_agent
    from backend.agents.distribution import DistributionRoutingAgent

    update_progress(job_id, "Loading company profile...", step=1, total=5)

    # 1. Load company
    if company_id:
        row = await db_module.get_company_by_id(company_id)
    else:
        row = await db_module.get_latest_company_row()

    if not row:
        raise ValueError("No company profile found. Please complete onboarding first.")

    company = CompanyProfile.from_db_row(row)

    update_progress(job_id, "Agent 2: Surfacing trend signals...", step=2, total=5)

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
        import json as _json

        # Prefer cached DB signals first so campaign generation remains fast/reliable.
        signals = []
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

        if not signals:
            from backend.agents.trend_intel import run_trend_agent

            try:
                signals = await asyncio.wait_for(
                    run_trend_agent(company=company, top_n=5),
                    timeout=_TREND_AGENT_TIMEOUT_S,
                )
            except Exception as e:
                log.warning("trend_agent_failed_using_fallback: %s", e)
                signals = _get_demo_trend_signals(company)

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
                "confidence_score": sig.confidence_score,
                "surfaced_at": sig.surfaced_at.isoformat(),
                "expires_at": sig.expires_at.isoformat() if sig.expires_at else None,
            }
            await db_module.insert_signal(sig_row)

    if not signals:
        raise ValueError("No trend signals available. Try refreshing signals first.")

    update_progress(job_id, "Agent 3: Generating campaign concepts...", step=3, total=5)

    # 3. Run Agent 3 — Campaign Generation
    prompt_weights = await _load_feedback_prompt_weights(company)
    concepts = []
    try:
        gen_response = await asyncio.wait_for(
            run_campaign_agent(
                company=company,
                signals=signals,
                prompt_weights=prompt_weights,
                n_concepts=n_concepts,
                persist=True,
            ),
            timeout=_CAMPAIGN_AGENT_TIMEOUT_S,
        )
        concepts = gen_response.concepts
    except Exception as e:
        log.warning("campaign_agent_failed_using_fallback: %s", e)

    if not concepts:
        concepts = _fallback_campaign_concepts(company, signals, n_concepts)
        await _persist_fallback_campaigns(concepts)

    update_progress(job_id, "Agent 4: Routing distribution channels...", step=4, total=5)

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
    try:
        distribution_timeout_s = max(_DISTRIBUTION_AGENT_TIMEOUT_S, 12 * max(1, len(concepts)))
        distribution_plans = await asyncio.wait_for(
            dist_agent.route_campaigns(concepts, company_dict),
            timeout=distribution_timeout_s,
        )
    except Exception as e:
        log.warning("distribution_agent_failed_using_fallback: %s", e)
        distribution_plans = _fallback_distribution_plans(company, concepts)

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
            await db_module.update_campaign_distribution(
                campaign_id=concept.id,
                channel_recommendation=concept.channel_recommendation.value,
                channel_reasoning=plan.reasoning or concept.channel_reasoning,
            )

    update_progress(job_id, "Finalizing campaign results...", step=5, total=5)

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
            _generate_campaigns_worker(job.job_id, req.company_id, req.signal_ids, req.n_concepts),
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


@router.get("/history")
async def campaign_history(
    company_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    """List campaign history from SQLite with lightweight aggregated metrics."""
    rows = await db_module.list_campaigns(
        company_id=company_id, status=status, limit=limit
    )
    history: List[dict] = []
    for row in rows:
        metrics = await db_module.get_campaign_metrics(row["id"])
        impressions = sum(int(m.get("impressions") or 0) for m in metrics)
        avg_engagement = (
            sum(float(m.get("engagement_rate") or 0) for m in metrics) / len(metrics)
            if metrics
            else 0.0
        )
        history.append(
            {
                **_row_to_api(row),
                "history_metrics": {
                    "impressions": impressions,
                    "engagement_rate": avg_engagement,
                    "samples": len(metrics),
                },
            }
        )
    return history


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
        "measured_at": datetime.now(UTC).isoformat(),
    })
    return {"metric_id": metric_id, "campaign_id": campaign_id, "status": "recorded"}
