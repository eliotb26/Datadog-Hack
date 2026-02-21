"""
SIGNAL — Agent 6: Content Strategy Agent
=========================================
Purpose : Decide what type(s) of content should be generated for a campaign concept.
LLM     : gemini-2.0-flash (classification + reasoning)
ADK     : Single LLM Agent with two tools:
            1. score_content_format  — score a single format's suitability
            2. format_strategy_output — validate and normalise the final strategy
Pattern : Takes a CampaignConcept + CompanyProfile context and recommends 1-3
          content formats ranked by expected performance.
"""
from __future__ import annotations

import asyncio
import functools
import json
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

import backend.database as _db_module
from backend.config import settings
from backend.integrations.braintrust_tracing import TracedRun
from backend.integrations.datadog_metrics import track_agent_run
from backend.models.content import (
    CONTENT_TYPE_META,
    ContentStrategy,
    ContentStrategyResponse,
    ContentType,
)

import os

load_dotenv()
log = structlog.get_logger(__name__)

STRATEGY_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

_VALID_TYPES = {t.value for t in ContentType}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — score_content_format
# ─────────────────────────────────────────────────────────────────────────────

def score_content_format(
    content_type: str,
    audience_fit: float,
    channel_alignment: float,
    production_complexity: float,
    reasoning: str,
) -> str:
    """Score how well a content format fits the campaign and audience.

    Args:
        content_type: One of tweet_thread, linkedin_article, blog_post,
            video_script, infographic, newsletter, instagram_carousel.
        audience_fit: How well this format reaches the target audience (0.0-1.0).
        channel_alignment: How well this format matches the recommended channel (0.0-1.0).
        production_complexity: How complex it is to produce (0.0=easy, 1.0=very complex).
        reasoning: One-line explanation of why this score.

    Returns:
        JSON string with composite score and breakdown.
    """
    issues: list[str] = []

    ct = content_type.lower().strip()
    if ct not in _VALID_TYPES:
        issues.append(f"Unknown content_type '{content_type}'. Valid: {sorted(_VALID_TYPES)}")

    for name, val in [("audience_fit", audience_fit), ("channel_alignment", channel_alignment)]:
        if not (0.0 <= val <= 1.0):
            issues.append(f"{name}={val} out of range [0,1]")

    composite = (audience_fit * 0.4 + channel_alignment * 0.4 + (1.0 - production_complexity) * 0.2)

    return json.dumps({
        "content_type": ct,
        "composite_score": round(composite, 3),
        "audience_fit": audience_fit,
        "channel_alignment": channel_alignment,
        "production_complexity": production_complexity,
        "reasoning": reasoning,
        "issues": issues,
        "is_valid": len(issues) == 0,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — format_strategy_output
# ─────────────────────────────────────────────────────────────────────────────

def format_strategy_output(
    strategies_json: str,
    campaign_id: str,
    company_id: str,
) -> str:
    """Validate and normalise the content strategy recommendations.

    Args:
        strategies_json: JSON array of strategy dicts from the LLM's reasoning.
        campaign_id: UUID of the campaign concept.
        company_id: UUID of the owning company.

    Returns:
        JSON with validated strategies and count.
    """
    try:
        raw = json.loads(strategies_json)
        if isinstance(raw, dict):
            raw = raw.get("strategies", [raw])
        if not isinstance(raw, list):
            raw = [raw]
    except (json.JSONDecodeError, TypeError) as exc:
        log.error("format_strategy_output.parse_failed", error=str(exc))
        return json.dumps({"error": str(exc), "strategies": [], "count": 0})

    validated: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ct = str(item.get("content_type", "blog_post")).lower().strip()
        if ct not in _VALID_TYPES:
            ct = "blog_post"

        outline = item.get("structure_outline", [])
        if isinstance(outline, str):
            outline = [s.strip() for s in outline.split(",") if s.strip()]

        try:
            strat = ContentStrategy(
                id=str(uuid.uuid4()),
                campaign_id=campaign_id,
                company_id=company_id,
                content_type=ContentType(ct),
                reasoning=str(item.get("reasoning", "")),
                target_length=str(item.get("target_length", "")),
                tone_direction=str(item.get("tone_direction", "")),
                structure_outline=outline,
                priority_score=float(item.get("priority_score", item.get("composite_score", 0.5))),
                visual_needed=bool(item.get("visual_needed", CONTENT_TYPE_META.get(ct, {}).get("visual_required", False))),
            )
            validated.append(strat.to_dict())
        except Exception as exc:  # noqa: BLE001
            log.warning("format_strategy_output.invalid", error=str(exc))
            continue

    log.info("format_strategy_output.complete", count=len(validated))
    return json.dumps(
        {"strategies": validated, "count": len(validated), "campaign_id": campaign_id},
        indent=2,
        default=str,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent instruction builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_instruction(
    company_name: str,
    industry: str,
    tone: str,
    audience: str,
    goals: str,
) -> str:
    type_catalog = "\n".join(
        f"  - **{meta['label']}** (`{ct}`): {meta['typical_length']}, "
        f"channel={meta['channel']}, visual={'required' if meta['visual_required'] else 'optional'}"
        for ct, meta in CONTENT_TYPE_META.items()
    )

    return f"""You are SIGNAL's Content Strategy Agent — you decide WHAT TYPE of content to create for a campaign.

## Company Context
- Company: {company_name}
- Industry: {industry}
- Tone: {tone}
- Audience: {audience}
- Goals: {goals}

## Available Content Formats
{type_catalog}

## Your Task
Given a campaign concept (headline, body copy, channel recommendation), recommend 1-3 content
formats ranked by expected performance. Consider:
1. Does the audience consume this format?
2. Does the recommended channel support it?
3. Can the campaign's message be effectively conveyed in this format?
4. Production complexity vs. expected ROI.

## Process
1. Analyse the campaign concept provided in the conversation.
2. For each candidate format, call `score_content_format` to evaluate fit.
3. Select the top 1-3 formats with the highest composite scores.
4. For each selected format, determine: target_length, tone_direction, structure_outline (list of section beats).
5. Call `format_strategy_output` ONCE with ALL strategies as a JSON array. This is your LAST action.

## Rules
- Always recommend at least 1 format.
- Never recommend more than 3 formats.
- structure_outline must be a JSON array of strings (section titles or beat descriptions).
- `format_strategy_output` MUST be the final tool call.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Agent factory
# ─────────────────────────────────────────────────────────────────────────────

def create_content_strategy_agent(
    company_name: str,
    industry: str,
    tone: str,
    audience: str,
    goals: str,
) -> Agent:
    if not settings.gemini_api_key_set:
        raise EnvironmentError("GEMINI_API_KEY is not set.")

    return Agent(
        name="content_strategy_agent",
        model=STRATEGY_MODEL,
        description="Decides the best content format(s) for a given campaign concept.",
        instruction=_build_instruction(company_name, industry, tone, audience, goals),
        tools=[score_content_format, format_strategy_output],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_content_strategy_agent(
    campaign_id: str,
    company_id: str,
    headline: str,
    body_copy: str,
    channel_recommendation: str,
    company_name: str = "",
    industry: str = "",
    tone: str = "",
    audience: str = "",
    goals: str = "",
    session_id: Optional[str] = None,
    persist: bool = True,
) -> ContentStrategyResponse:
    """Run Agent 6 to decide content format(s) for a campaign concept."""

    captured: list[ContentStrategy] = []

    @functools.wraps(format_strategy_output)
    def _capturing_format_strategy_output(
        strategies_json: str, campaign_id: str, company_id: str
    ) -> str:
        result = format_strategy_output(strategies_json, campaign_id, company_id)
        try:
            data = json.loads(result)
            for row in data.get("strategies", []):
                try:
                    captured.append(ContentStrategy(**row))
                except Exception:
                    pass
        except Exception:
            pass
        return result

    if not settings.gemini_api_key_set:
        raise EnvironmentError("GEMINI_API_KEY is not set.")
    agent = Agent(
        name="content_strategy_agent",
        model=STRATEGY_MODEL,
        description="Decides the best content format(s) for a given campaign concept.",
        instruction=_build_instruction(company_name, industry, tone, audience, goals),
        tools=[score_content_format, _capturing_format_strategy_output],
    )
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="signal", session_service=session_service)

    sid = session_id or f"strategy-{campaign_id}-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(app_name="signal", user_id=company_id, session_id=sid)

    prompt = (
        f"Recommend content formats for this campaign:\n\n"
        f"**Headline**: {headline}\n"
        f"**Body Copy**: {body_copy}\n"
        f"**Recommended Channel**: {channel_recommendation}\n\n"
        f"Campaign ID: {campaign_id}\n"
        f"Company ID: {company_id}\n"
    )
    message = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])

    log.info("content_strategy_agent_starting", campaign_id=campaign_id, company=company_name)
    start_time = time.perf_counter()
    strategies: list[ContentStrategy] = []

    bt_input = {
        "campaign_id": campaign_id,
        "company_id": company_id,
        "headline": headline,
        "channel": channel_recommendation,
    }

    with TracedRun("content_strategy", input=bt_input) as bt_span:
        try:
            async for event in runner.run_async(
                user_id=company_id, session_id=sid, new_message=message
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    text = event.content.parts[0].text or ""
                    text_strategies = _extract_strategies(text, campaign_id, company_id)
                    strategies = text_strategies if text_strategies else captured

            if not strategies and captured:
                strategies = captured

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            track_agent_run(
                agent_name="content_strategy",
                items_produced=len(strategies),
                company_id=company_id,
                latency_ms=elapsed_ms,
                success=True,
            )
            log.info(
                "content_strategy_agent_complete",
                strategies=len(strategies),
                elapsed_ms=elapsed_ms,
            )
            if strategies:
                bt_span.log_output(
                    output={"strategies": [s.to_dict() for s in strategies], "count": len(strategies)},
                    scores={"strategy_count": len(strategies)},
                    metadata={"latency_ms": elapsed_ms},
                )
        except asyncio.CancelledError:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            track_agent_run(
                agent_name="content_strategy",
                items_produced=len(strategies),
                company_id=company_id,
                latency_ms=elapsed_ms,
                success=False,
            )
            log.warning(
                "content_strategy_agent_cancelled",
                campaign_id=campaign_id,
                company_id=company_id,
                elapsed_ms=elapsed_ms,
            )
            raise
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            track_agent_run(
                agent_name="content_strategy",
                items_produced=0,
                company_id=company_id,
                latency_ms=elapsed_ms,
                success=False,
            )
            log.error("content_strategy_agent_error", error=str(exc))
            raise

    if persist and strategies:
        await _persist_strategies(strategies)

    return ContentStrategyResponse(
        campaign_id=campaign_id,
        strategies=strategies,
        latency_ms=elapsed_ms,
        success=len(strategies) > 0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_strategies(
    text: str, campaign_id: str, company_id: str
) -> list[ContentStrategy]:
    import re

    json_pattern = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", re.MULTILINE)
    candidates = json_pattern.findall(text)
    if not candidates:
        candidates = re.findall(r"(\{[^{}]{80,}\}|\[[^\[\]]{80,}\])", text)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            raw_list = (
                data.get("strategies", [])
                if isinstance(data, dict)
                else data
            )
            if not isinstance(raw_list, list):
                continue

            result: list[ContentStrategy] = []
            for item in raw_list:
                ct = str(item.get("content_type", "blog_post")).lower()
                if ct not in _VALID_TYPES:
                    ct = "blog_post"
                outline = item.get("structure_outline", [])
                if isinstance(outline, str):
                    outline = [s.strip() for s in outline.split(",") if s.strip()]
                result.append(
                    ContentStrategy(
                        campaign_id=campaign_id,
                        company_id=company_id,
                        content_type=ContentType(ct),
                        reasoning=str(item.get("reasoning", "")),
                        target_length=str(item.get("target_length", "")),
                        tone_direction=str(item.get("tone_direction", "")),
                        structure_outline=outline,
                        priority_score=float(item.get("priority_score", 0.5)),
                        visual_needed=bool(item.get("visual_needed", False)),
                    )
                )
            if result:
                return result
        except (json.JSONDecodeError, TypeError):
            continue
    return []


async def _persist_strategies(strategies: list[ContentStrategy]) -> None:
    db_path = _db_module.DB_PATH
    await _db_module.init_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        for strat in strategies:
            row = strat.to_db_row()
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
                row,
            )
        await db.commit()
    log.info("content_strategies_persisted", count=len(strategies))


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main() -> None:
        print(f"\n{'=' * 60}")
        print("  SIGNAL — Content Strategy Agent (Agent 6)")
        print(f"{'=' * 60}\n")

        response = await run_content_strategy_agent(
            campaign_id="test-campaign-001",
            company_id="test-company-001",
            headline="AI Coding Tools Won't Replace You — They'll Make You Dangerous",
            body_copy="As prediction markets signal rising confidence in AI augmentation over replacement, now is the time to position your developer tools brand as the ally, not the threat.",
            channel_recommendation="linkedin",
            company_name="NovaTech",
            industry="SaaS / Developer Tools",
            tone="bold, technical, slightly witty",
            audience="software engineers and CTOs",
            goals="drive developer sign-ups and community growth",
            persist=False,
        )

        if not response.strategies:
            print("No strategies generated. Check GEMINI_API_KEY.")
            return

        print(f"Generated {len(response.strategies)} strategy(ies) in {response.latency_ms}ms\n")
        for i, s in enumerate(response.strategies, 1):
            print(f"Strategy {i}: {s.content_type.value}")
            print(f"  Priority : {s.priority_score:.0%}")
            print(f"  Length   : {s.target_length}")
            print(f"  Tone     : {s.tone_direction}")
            print(f"  Outline  : {s.structure_outline}")
            print(f"  Reasoning: {s.reasoning[:120]}...")
            print()

    asyncio.run(_main())
