"""
SIGNAL — Agent 3: Campaign Generation Agent
============================================
Purpose : Generate 3-5 campaign concepts from a brand profile + trend signals.
LLM     : gemini-2.0-flash (creative generation with brand voice adherence)
ADK     : Single LLM Agent with two tools:
            1. validate_campaign_concept  — quality-checks a single concept
            2. format_campaign_concepts   — validates and normalises final output JSON
Pattern : Brand profile + prompt_weights injected into system instruction.
          Weights are updated by Loop 1 (Feedback Loop Agent) over time.
"""
from __future__ import annotations

import asyncio
import functools
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiosqlite
import structlog
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from pydantic import ValidationError

import backend.database as _db_module
from backend.config import settings
from backend.integrations.braintrust_tracing import (
    TracedRun,
    score_brand_alignment,
    score_campaign_concept,
)
from backend.integrations.datadog_metrics import (
    track_campaign_agent_run,
    track_campaign_approved,
    track_campaign_blocked_safety,
    track_modulate_safety_check,
)
from backend.integrations.gemini_media import generate_image_asset
from backend.integrations.modulate_safety import screen_campaign as modulate_screen
from backend.models.campaign import (
    CampaignConcept,
    CampaignGenerationResponse,
    Channel,
)
from backend.models.company import CompanyProfile
from backend.models.signal import TrendSignal

load_dotenv()
log = structlog.get_logger(__name__)

CAMPAIGN_GEN_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# Valid channel values for normalisation
_VALID_CHANNELS = {c.value for c in Channel}


# ──────────────────────────────────────────────────────────────────────────────
# Tool 1 — validate_campaign_concept
# ──────────────────────────────────────────────────────────────────────────────

def validate_campaign_concept(
    headline: str,
    body_copy: str,
    channel_recommendation: str,
    confidence_score: float,
) -> str:
    """Quality-check a single campaign concept before including it in the final output.

    Args:
        headline: The campaign headline to check.
        body_copy: The campaign body copy to check.
        channel_recommendation: Proposed channel — must be one of twitter, linkedin,
            instagram, or newsletter.
        confidence_score: Agent's confidence in this concept (0.0 to 1.0).

    Returns:
        JSON string with fields:
          - is_valid (bool)
          - issues (list[str])
          - adjusted_confidence (float)
          - message (str)
    """
    issues: List[str] = []

    if not headline or not headline.strip():
        issues.append("headline is empty")
    elif len(headline.split()) > 20:
        issues.append(f"headline too long ({len(headline.split())} words — aim for ≤15)")

    word_count = len(body_copy.split()) if body_copy else 0
    if word_count < 20:
        issues.append(f"body_copy too short ({word_count} words — aim for 50-150)")
    elif word_count > 200:
        issues.append(f"body_copy too long ({word_count} words — aim for 50-150)")

    ch = channel_recommendation.lower() if channel_recommendation else ""
    if ch not in _VALID_CHANNELS:
        issues.append(
            f"channel '{channel_recommendation}' is not valid — "
            f"must be one of {sorted(_VALID_CHANNELS)}"
        )

    if not (0.0 <= confidence_score <= 1.0):
        issues.append(f"confidence_score {confidence_score} is out of range [0, 1]")

    is_valid = len(issues) == 0
    # Penalise confidence slightly if there are minor issues
    adjusted_confidence = max(0.0, confidence_score - 0.1 * len(issues))

    return json.dumps(
        {
            "is_valid": is_valid,
            "issues": issues,
            "adjusted_confidence": round(adjusted_confidence, 3),
            "message": (
                "Concept passes quality checks."
                if is_valid
                else f"Found {len(issues)} issue(s): {'; '.join(issues)}"
            ),
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tool 2 — format_campaign_concepts
# ──────────────────────────────────────────────────────────────────────────────

def format_campaign_concepts(
    concepts_json: str,
    company_id: str,
    trend_signal_id: str,
) -> str:
    """Validate and normalise the LLM-generated campaign concepts into the CampaignConcept schema.

    This is the final tool called by the agent. It validates every concept against
    the Pydantic schema, normalises channel names, and returns a clean JSON payload
    ready for persistence.

    Args:
        concepts_json: JSON string — a list of concept dicts from the LLM's reasoning.
        company_id: UUID of the company these concepts were generated for.
        trend_signal_id: UUID (or Polymarket ID) of the primary trend signal used.

    Returns:
        JSON string with fields:
          - concepts: list of validated CampaignConcept dicts
          - count: number of valid concepts
          - company_id: echoed back
    """
    try:
        raw = json.loads(concepts_json)
        if isinstance(raw, dict):
            raw = raw.get("concepts", raw.get("campaign_concepts", [raw]))
        if not isinstance(raw, list):
            raw = [raw]
    except (json.JSONDecodeError, TypeError) as exc:
        log.error("format_campaign_concepts.parse_failed", error=str(exc))
        return json.dumps({"error": f"JSON parse failed: {exc}", "concepts": [], "count": 0})

    validated: List[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        # Normalise channel casing
        ch = str(item.get("channel_recommendation", "twitter")).lower()
        if ch not in _VALID_CHANNELS:
            ch = "twitter"
        item["channel_recommendation"] = ch

        try:
            concept = CampaignConcept(
                id=str(uuid.uuid4()),
                company_id=company_id,
                trend_signal_id=trend_signal_id,
                headline=str(item.get("headline", "")),
                body_copy=str(item.get("body_copy", "")),
                visual_direction=str(item.get("visual_direction", "")),
                confidence_score=float(item.get("confidence_score", 0.7)),
                channel_recommendation=ch,
                channel_reasoning=str(item.get("channel_reasoning", "")),
            )
            validated.append(concept.to_dict())
        except (ValidationError, Exception) as exc:  # noqa: BLE001
            log.warning("format_campaign_concepts.concept_invalid", error=str(exc), item=item)
            continue

    log.info("format_campaign_concepts.complete", count=len(validated))
    return json.dumps(
        {"concepts": validated, "count": len(validated), "company_id": company_id},
        indent=2,
        default=str,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Agent instruction builder
# ──────────────────────────────────────────────────────────────────────────────

def _build_instruction(
    company: CompanyProfile,
    prompt_weights: Dict[str, Any],
    n_concepts: int,
) -> str:
    """Build the per-run system instruction with company profile and learned weights."""
    tone_weight = float(prompt_weights.get("tone_weight", 1.0))
    learned = prompt_weights.get("learned_preferences", "")
    learned_section = (
        f"\nLearned style preferences (from past performance):\n{learned}"
        if learned
        else ""
    )
    history_sample = (
        "\n".join(f"  - {h}" for h in company.content_history[:3])
        if company.content_history
        else "  - (no history yet)"
    )

    return f"""You are SIGNAL's Campaign Generation Agent — a creative strategist for {company.name}.

## Company Profile
- Name:     {company.name}
- Industry: {company.industry}
- Voice:    {company.tone_of_voice or "professional"} (weight: {tone_weight:.2f}× — higher means lean harder into this tone)
- Audience: {company.target_audience or "general audience"}
- Goals:    {company.campaign_goals or "brand awareness and engagement"}
- Competitors: {", ".join(company.competitors) if company.competitors else "N/A"}

## Past Content Style
{history_sample}
{learned_section}

## Your Task
Generate exactly {n_concepts} campaign concepts for the trend signal(s) provided in the conversation.
Each concept must be DISTINCT in angle, tone, and channel.

## Process
1. Read the trend signal(s) carefully.
2. For each concept, draft: headline, body_copy (50-150 words), visual_direction, confidence_score (0-1),
   channel_recommendation (twitter/linkedin/instagram/newsletter), and channel_reasoning.
3. Call `validate_campaign_concept` for each concept to self-check quality.
4. Revise any concept that fails validation.
5. Call `format_campaign_concepts` ONCE with ALL final concepts as a JSON array. This is your LAST action.

## Rules
- Never use placeholder text (e.g., "Lorem ipsum")
- Body copy must be ready to publish — no brackets or variables
- Confidence scores must reflect genuine quality assessment, not always be 0.9
- `format_campaign_concepts` MUST be the final tool call
"""


# ──────────────────────────────────────────────────────────────────────────────
# Agent factory
# ──────────────────────────────────────────────────────────────────────────────

def create_campaign_gen_agent(
    company: CompanyProfile,
    prompt_weights: Dict[str, Any],
    n_concepts: int,
) -> Agent:
    """Build a per-run Campaign Generation Agent with company profile baked into the instruction."""
    if not settings.gemini_api_key_set:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Please add it to your .env file.\n"
            "Get a key at: https://aistudio.google.com/apikey"
        )

    return Agent(
        name="campaign_generation_agent",
        model=CAMPAIGN_GEN_MODEL,
        description="Generates campaign concepts from brand profile and trend signals.",
        instruction=_build_instruction(company, prompt_weights, n_concepts),
        tools=[validate_campaign_concept, format_campaign_concepts],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Public runner function
# ──────────────────────────────────────────────────────────────────────────────

async def run_campaign_agent(
    company: CompanyProfile,
    signals: List[TrendSignal],
    prompt_weights: Optional[Dict[str, Any]] = None,
    n_concepts: int = 3,
    session_id: Optional[str] = None,
    persist: bool = True,
) -> CampaignGenerationResponse:
    """Run one full Campaign Generation Agent cycle.

    Args:
        company:        The CompanyProfile to generate campaigns for.
        signals:        List of TrendSignal objects (from Agent 2).
        prompt_weights: Learned weights from Loop 1 (tone_weight, learned_preferences, etc.).
        n_concepts:     How many campaign concepts to generate (1-5).
        session_id:     Optional trace/session ID.
        persist:        Whether to save generated campaigns to SQLite.

    Returns:
        CampaignGenerationResponse with a list of CampaignConcept objects.
    """
    weights = prompt_weights or {}
    n_concepts = max(1, min(5, n_concepts))

    # Capture concepts directly from the format_campaign_concepts tool call so
    # we don't rely on parsing them back out of the LLM's prose final response.
    _tool_captured: List[CampaignConcept] = []

    @functools.wraps(format_campaign_concepts)
    def _capturing_format(concepts_json: str, company_id: str, trend_signal_id: str) -> str:
        result = format_campaign_concepts(concepts_json, company_id, trend_signal_id)
        try:
            data = json.loads(result)
            for c in data.get("concepts", []):
                try:
                    _tool_captured.append(CampaignConcept(**c))
                except Exception:
                    pass
        except Exception:
            pass
        return result

    agent = Agent(
        name="campaign_generation_agent",
        model=CAMPAIGN_GEN_MODEL,
        description="Generates campaign concepts from brand profile and trend signals.",
        instruction=_build_instruction(company, weights, n_concepts),
        tools=[validate_campaign_concept, _capturing_format],
    )
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="signal",
        session_service=session_service,
    )

    sid = session_id or f"campaign-{company.id}-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name="signal",
        user_id=company.id,
        session_id=sid,
    )

    prompt = _build_user_prompt(company, signals, n_concepts)
    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    log.info(
        "campaign_agent_starting",
        company=company.name,
        signals=len(signals),
        n_concepts=n_concepts,
        session_id=sid,
    )

    bt_input = {
        "company_id": company.id,
        "company_name": company.name,
        "industry": company.industry,
        "tone_of_voice": company.tone_of_voice,
        "target_audience": company.target_audience,
        "campaign_goals": company.campaign_goals,
        "n_concepts": n_concepts,
        "signal_titles": [s.title for s in signals],
        "session_id": sid,
    }

    start_time = time.perf_counter()
    concepts: List[CampaignConcept] = []

    with TracedRun("campaign_gen", input=bt_input) as bt_span:
        try:
            async for event in runner.run_async(
                user_id=company.id,
                session_id=sid,
                new_message=message,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_text = event.content.parts[0].text or ""
                    log.debug("campaign_agent_final_response", preview=final_text[:200])
                    text_concepts = _extract_concepts_from_response(final_text, company.id, signals)
                    concepts = text_concepts if text_concepts else _tool_captured

            # Final fallback: if event loop ended without setting concepts, use tool-captured
            if not concepts and _tool_captured:
                concepts = _tool_captured

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            track_campaign_agent_run(
                concepts_generated=len(concepts),
                company_id=company.id,
                latency_ms=elapsed_ms,
                success=True,
            )
            log.info(
                "campaign_agent_complete",
                company=company.name,
                concepts=len(concepts),
                elapsed_ms=elapsed_ms,
            )

            # Braintrust: log output and scores
            if concepts:
                quality_scores = [score_campaign_concept(c) for c in concepts]
                brand_scores = [score_brand_alignment(c, company) for c in concepts]
                bt_span.log_output(
                    output={
                        "concepts": [c.to_dict() for c in concepts],
                        "count": len(concepts),
                        "latency_ms": elapsed_ms,
                    },
                    scores={
                        "quality": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
                        "brand_alignment": sum(brand_scores) / len(brand_scores) if brand_scores else 0,
                    },
                    metadata={"latency_ms": elapsed_ms, "n_concepts": len(concepts)},
                )

        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            track_campaign_agent_run(
                concepts_generated=0,
                company_id=company.id,
                latency_ms=elapsed_ms,
                success=False,
            )
            log.error("campaign_agent_error", company=company.name, error=str(exc))
            raise

    if concepts:
        concepts = _run_safety_checks(concepts, company.id)
        await _attach_media_assets(concepts, company)

    if persist and concepts:
        await _persist_campaigns(concepts)

    primary_signal_ids = [s.id for s in signals]

    return CampaignGenerationResponse(
        company_id=company.id,
        trend_signal_ids=primary_signal_ids,
        concepts=concepts,
        latency_ms=elapsed_ms,
        success=len(concepts) > 0,
    )


async def _attach_media_assets(
    concepts: List[CampaignConcept],
    company: CompanyProfile,
) -> None:
    """Generate Gemini image assets for campaign concepts when visuals are enabled."""
    if not settings.ENABLE_GEMINI_MEDIA:
        return

    async def _one(concept: CampaignConcept) -> None:
        if concept.visual_asset_url:
            return
        prompt = (
            f"Create a campaign key visual for '{concept.headline}'. "
            f"Brand: {company.name} ({company.industry}). "
            f"Direction: {concept.visual_direction or 'clean, modern promotional creative'}."
        )
        asset = await generate_image_asset(
            prompt=prompt,
            aspect_ratio="16:9",
            style_hint=company.visual_style or "",
        )
        if asset:
            concept.visual_asset_url = asset.asset_url

    await asyncio.gather(*(_one(c) for c in concepts))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _build_user_prompt(
    company: CompanyProfile,
    signals: List[TrendSignal],
    n_concepts: int,
) -> str:
    """Format the trend signals into a structured user message."""
    lines = [
        f"Generate {n_concepts} campaign concept(s) for {company.name} based on these trend signal(s):\n"
    ]
    for i, sig in enumerate(signals, 1):
        relevance = sig.relevance_scores.get(company.id, 0.5)
        lines.append(f"## Signal {i}: {sig.title}")
        lines.append(f"   Category   : {sig.category or 'general'}")
        lines.append(f"   Probability: {sig.probability:.0%}")
        lines.append(f"   Momentum   : {sig.probability_momentum:+.2f} (positive = rising)")
        lines.append(f"   Volume     : ${sig.volume:,.0f}" if sig.volume else "   Volume     : N/A")
        lines.append(f"   Relevance  : {relevance:.0%} to {company.name}")
        lines.append("")
    return "\n".join(lines)


def _extract_concepts_from_response(
    text: str,
    company_id: str,
    signals: List[TrendSignal],
) -> List[CampaignConcept]:
    """Parse CampaignConcept objects from the agent's final text response.

    The `format_campaign_concepts` tool already validated and returned a JSON
    payload; the LLM may echo it in its final message.
    """
    import re

    primary_signal_id = signals[0].id if signals else "unknown"

    # Try JSON code blocks first
    json_pattern = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", re.MULTILINE)
    candidates = json_pattern.findall(text)
    if not candidates:
        candidates = re.findall(r"(\{[^{}]{100,}\}|\[[^\[\]]{100,}\])", text)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            raw_list = (
                data.get("concepts", data.get("campaign_concepts", []))
                if isinstance(data, dict)
                else data
            )
            if not isinstance(raw_list, list):
                continue

            result: List[CampaignConcept] = []
            for item in raw_list:
                try:
                    ch = str(item.get("channel_recommendation", "twitter")).lower()
                    if ch not in _VALID_CHANNELS:
                        ch = "twitter"
                    result.append(
                        CampaignConcept(
                            company_id=company_id,
                            trend_signal_id=primary_signal_id,
                            headline=str(item.get("headline", "")),
                            body_copy=str(item.get("body_copy", "")),
                            visual_direction=str(item.get("visual_direction", "")),
                            confidence_score=float(item.get("confidence_score", 0.7)),
                            channel_recommendation=ch,
                            channel_reasoning=str(item.get("channel_reasoning", "")),
                        )
                    )
                except Exception:  # noqa: BLE001
                    continue

            if result:
                return result
        except (json.JSONDecodeError, TypeError):
            continue

    return []


def _run_safety_checks(
    concepts: List[CampaignConcept], company_id: str
) -> List[CampaignConcept]:
    """Run Modulate safety screening on every concept and annotate in-place.

    Fills in `safety_score` and `safety_passed` on each concept.
    Blocked concepts are kept in the list but marked `safety_passed=False`
    so the UI can show the red safety badge without losing the content.
    """
    for concept in concepts:
        try:
            result = modulate_screen(
                campaign_id=concept.id,
                headline=concept.headline,
                body_copy=concept.body_copy,
                company_id=company_id,
            )
            concept.safety_score = result.toxicity_score
            concept.safety_passed = not result.blocked

            track_modulate_safety_check(
                company_id=company_id,
                blocked=result.blocked,
                toxicity_score=result.toxicity_score,
                latency_ms=float(result.latency_ms or 0),
                method=result.screening_method,
            )

            if result.blocked:
                track_campaign_blocked_safety(
                    company_id=company_id,
                    safety_score=result.toxicity_score,
                )
                log.warning(
                    "campaign_blocked_safety",
                    campaign_id=concept.id,
                    headline=concept.headline[:60],
                    score=result.toxicity_score,
                    categories=[c.value for c in result.categories],
                )
            else:
                track_campaign_approved(company_id=company_id)
                log.info(
                    "campaign_safety_passed",
                    campaign_id=concept.id,
                    score=result.toxicity_score,
                )

        except Exception as exc:  # noqa: BLE001
            log.warning(
                "campaign_safety_check_failed",
                campaign_id=concept.id,
                error=str(exc),
            )
            concept.safety_score = 0.0
            concept.safety_passed = True

    return concepts


async def _persist_campaigns(concepts: List[CampaignConcept]) -> None:
    """Write CampaignConcept objects to the campaigns SQLite table."""
    db_path = _db_module.DB_PATH
    await _db_module.init_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        for concept in concepts:
            row = concept.to_db_row()
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
                row,
            )
        await db.commit()
    log.info("campaigns_persisted", count=len(concepts))


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point for quick manual testing
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Agent 3 — Campaign Generation Agent")
    parser.add_argument("--company", default="NovaTech", help="Company name")
    parser.add_argument("--industry", default="SaaS / Developer Tools", help="Industry")
    parser.add_argument("--audience", default="software engineers and CTOs", help="Target audience")
    parser.add_argument("--goals", default="drive developer sign-ups and community growth", help="Goals")
    parser.add_argument("--n", type=int, default=3, help="Number of concepts to generate")
    args = parser.parse_args()

    sample_company = CompanyProfile(
        name=args.company,
        industry=args.industry,
        tone_of_voice="bold, technical, slightly witty",
        target_audience=args.audience,
        campaign_goals=args.goals,
        competitors=["GitHub Copilot", "Cursor", "Tabnine"],
        content_history=[
            "We shipped v2.0 — now 3× faster",
            "How we cut CI costs by 40% in one week",
        ],
        visual_style="dark mode, code-forward, minimal",
    )

    sample_signals = [
        TrendSignal(
            polymarket_market_id="pm-12345",
            title="Will AI coding tools replace 50% of junior dev roles by 2026?",
            category="tech",
            probability=0.38,
            probability_momentum=0.07,
            volume=850_000,
            volume_velocity=0.18,
            relevance_scores={sample_company.id: 0.92},
            confidence_score=0.85,
        )
    ]

    async def _main() -> None:
        print(f"\n{'=' * 60}")
        print("  SIGNAL — Campaign Generation Agent")
        print(f"  Company : {sample_company.name} ({sample_company.industry})")
        print(f"  Signal  : {sample_signals[0].title[:60]}...")
        print(f"{'=' * 60}\n")

        response = await run_campaign_agent(
            company=sample_company,
            signals=sample_signals,
            n_concepts=args.n,
            persist=False,
        )

        if not response.concepts:
            print("No concepts generated. Check GEMINI_API_KEY and retry.")
            return

        print(f"✓ {len(response.concepts)} concept(s) generated in {response.latency_ms}ms\n")
        for i, c in enumerate(response.concepts, 1):
            print(f"Concept {i}: {c.headline}")
            print(f"  Channel    : {c.channel_recommendation.value}")
            print(f"  Confidence : {c.confidence_score:.0%}")
            print(f"  Body       : {c.body_copy[:120]}...")
            print(f"  Visual     : {c.visual_direction[:80]}...")
            print()

    asyncio.run(_main())
