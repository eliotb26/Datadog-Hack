"""
SIGNAL — Agent 7: Content Production Agent
============================================
Purpose : Generate full-length, publish-ready content from a ContentStrategy.
LLM     : gemini-2.0-flash (long-form creative generation)
ADK     : Single LLM Agent with two tools:
            1. validate_content_piece  — quality-check the generated content
            2. format_content_output   — validate and normalise the final piece
Pattern : Takes a ContentStrategy (from Agent 6) + original CampaignConcept
          and produces the actual content — articles, threads, scripts, etc.
"""
from __future__ import annotations

import asyncio
import functools
import json
import re
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
from backend.integrations.gemini_media import generate_image_asset, generate_video_asset
from backend.models.content import (
    CONTENT_TYPE_META,
    ContentPiece,
    ContentProductionResponse,
    ContentStrategy,
    ContentType,
)

import os

load_dotenv()
log = structlog.get_logger(__name__)

PRODUCTION_MODEL = os.getenv("CONTENT_PRODUCTION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
FALLBACK_MODELS = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.0-flash,gemini-1.5-flash")

_VALID_TYPES = {t.value for t in ContentType}

_LENGTH_GUIDELINES = {
    "tweet_thread": "Each tweet ≤280 characters. 3-8 tweets. Number them [1/N]. First tweet is the hook.",
    "linkedin_article": "800-1500 words. Use subheadings. Professional but engaging. Include a call-to-action.",
    "blog_post": "1000-2500 words. SEO-friendly structure with H2/H3. Include intro, body sections, conclusion with CTA.",
    "video_script": "60-180 seconds spoken. Format: [VISUAL] description + [NARRATOR] dialogue. Include intro hook, key points, CTA.",
    "infographic": "5-8 data panels. For each panel: panel_title, stat/data_point, supporting_copy (1 sentence). Plus a header and footer CTA.",
    "newsletter": "500-1000 words. Warm opening, 2-3 key sections, links, sign-off. Conversational tone.",
    "instagram_carousel": "5-10 slides. For each slide: slide_number, headline (≤8 words), body (≤30 words), visual_note. Plus a CTA slide.",
}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — validate_content_piece
# ─────────────────────────────────────────────────────────────────────────────

def validate_content_piece(
    content_type: str,
    title: str,
    body: str,
    word_count: int,
) -> str:
    """Quality-check a generated content piece before finalising.

    Args:
        content_type: The format type.
        title: Content title / headline.
        body: The full content body.
        word_count: Approximate word count of the body.

    Returns:
        JSON with is_valid, issues list, and quality_score.
    """
    issues: list[str] = []

    if not title or not title.strip():
        issues.append("Title is empty")

    if not body or len(body.strip()) < 50:
        issues.append("Body is too short (< 50 chars)")

    ct = content_type.lower().strip()

    if ct == "tweet_thread" and word_count > 2000:
        issues.append("Tweet thread body too long")
    elif ct == "blog_post" and word_count < 300:
        issues.append(f"Blog post too short ({word_count} words, aim for 1000+)")
    elif ct == "linkedin_article" and word_count < 200:
        issues.append(f"LinkedIn article too short ({word_count} words, aim for 800+)")

    if "[placeholder]" in body.lower() or "lorem ipsum" in body.lower():
        issues.append("Contains placeholder text")

    quality = max(0.0, 1.0 - 0.15 * len(issues))

    return json.dumps({
        "is_valid": len(issues) == 0,
        "issues": issues,
        "quality_score": round(quality, 3),
        "message": "Content passes quality checks." if not issues else f"{len(issues)} issue(s): {'; '.join(issues)}",
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — format_content_output
# ─────────────────────────────────────────────────────────────────────────────

def format_content_output(
    content_json: str,
    strategy_id: str,
    campaign_id: str,
    company_id: str,
) -> str:
    """Validate and normalise the generated content piece(s).

    Args:
        content_json: JSON string with the content piece(s).
        strategy_id: UUID of the ContentStrategy this was produced from.
        campaign_id: UUID of the parent campaign.
        company_id: UUID of the owning company.

    Returns:
        JSON with validated pieces and count.
    """
    try:
        raw = json.loads(content_json)
        if isinstance(raw, dict):
            raw = raw.get("pieces", raw.get("content_pieces", [raw]))
        if not isinstance(raw, list):
            raw = [raw]
    except (json.JSONDecodeError, TypeError) as exc:
        log.error("format_content_output.parse_failed", error=str(exc))
        return json.dumps({"error": str(exc), "pieces": [], "count": 0})

    validated: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ct = str(item.get("content_type", "blog_post")).lower().strip()
        if ct not in _VALID_TYPES:
            ct = "blog_post"

        body = str(item.get("body", ""))
        wc = len(body.split())

        try:
            piece = ContentPiece(
                id=str(uuid.uuid4()),
                strategy_id=strategy_id,
                campaign_id=campaign_id,
                company_id=company_id,
                content_type=ContentType(ct),
                title=str(item.get("title", "")),
                body=body,
                summary=str(item.get("summary", "")),
                word_count=wc,
                visual_prompt=item.get("visual_prompt"),
                quality_score=float(item.get("quality_score", 0.7)),
                brand_alignment=float(item.get("brand_alignment", 0.7)),
            )
            validated.append(piece.to_dict())
        except Exception as exc:  # noqa: BLE001
            log.warning("format_content_output.invalid", error=str(exc))
            continue

    log.info("format_content_output.complete", count=len(validated))
    return json.dumps(
        {"pieces": validated, "count": len(validated), "strategy_id": strategy_id},
        indent=2,
        default=str,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent instruction builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_instruction(
    company_name: str,
    tone: str,
    audience: str,
    goals: str,
    content_type: str,
    target_length: str,
    tone_direction: str,
    structure_outline: list[str],
) -> str:
    format_guide = _LENGTH_GUIDELINES.get(content_type, "Follow standard best practices.")
    meta = CONTENT_TYPE_META.get(content_type, {})
    outline_text = "\n".join(f"  {i}. {beat}" for i, beat in enumerate(structure_outline, 1)) if structure_outline else "  (no outline provided — use best judgment)"

    return f"""You are SIGNAL's Content Production Agent — you write publish-ready content.

## Company Context
- Company: {company_name}
- Brand Tone: {tone}
- Target Audience: {audience}
- Campaign Goals: {goals}

## Content Format
- Type: **{meta.get('label', content_type)}** (`{content_type}`)
- Target Length: {target_length}
- Tone Direction: {tone_direction}
- Visual Required: {'Yes' if meta.get('visual_required') else 'No'}

## Format Guidelines
{format_guide}

## Required Structure
{outline_text}

## Your Task
Write ONE complete, publish-ready content piece following the format above.
The content should be based on the campaign concept provided in the conversation.

## Process
1. Read the campaign headline and body copy carefully.
2. Write the full content following the structure outline and format guidelines.
3. Call `validate_content_piece` to self-check quality.
4. If validation fails, revise and re-validate.
5. Call `format_content_output` ONCE with the final piece. This is your LAST action.

## Rules
- NO placeholder text (no brackets, no "insert X here")
- Content must be ready to copy-paste and publish
- Match the brand tone precisely
- For tweet threads: return body as a JSON array of tweet strings
- For infographics/carousels: return body as a JSON array of slide objects
- For articles/posts: return body as markdown text
- Include a visual_prompt if the format benefits from imagery (a detailed Gemini image/video prompt)
- `format_content_output` MUST be the final tool call
"""


# ─────────────────────────────────────────────────────────────────────────────
# Agent factory
# ─────────────────────────────────────────────────────────────────────────────

def create_content_production_agent(
    company_name: str,
    tone: str,
    audience: str,
    goals: str,
    strategy: ContentStrategy,
) -> Agent:
    if not settings.gemini_api_key_set:
        raise EnvironmentError("OPENROUTER_API_KEY is not set.")

    return Agent(
        name="content_production_agent",
        model=PRODUCTION_MODEL,
        description="Generates full-length, publish-ready content from a content strategy.",
        instruction=_build_instruction(
            company_name=company_name,
            tone=tone,
            audience=audience,
            goals=goals,
            content_type=strategy.content_type.value,
            target_length=strategy.target_length,
            tone_direction=strategy.tone_direction,
            structure_outline=strategy.structure_outline,
        ),
        tools=[validate_content_piece, format_content_output],
    )


def _candidate_models(primary: str) -> list[str]:
    models: list[str] = []
    for model in [primary, *[m.strip() for m in FALLBACK_MODELS.split(",")]]:
        if model and model not in models:
            models.append(model)
    return models


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).upper()
    return "RESOURCE_EXHAUSTED" in msg or " 429 " in f" {msg} " or "ERROR CODE 429" in msg


def _retry_delay_seconds(exc: Exception) -> float:
    msg = str(exc)
    for pattern in [r"retry in ([0-9]*\.?[0-9]+)s", r"'retryDelay': '([0-9]+)s'"]:
        match = re.search(pattern, msg, flags=re.IGNORECASE)
        if match:
            return max(0.0, float(match.group(1)))
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Public runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_content_production_agent(
    strategy: ContentStrategy,
    campaign_headline: str,
    campaign_body_copy: str,
    company_name: str = "",
    tone: str = "",
    audience: str = "",
    goals: str = "",
    session_id: Optional[str] = None,
    persist: bool = True,
) -> ContentProductionResponse:
    """Run Agent 7 to produce full content from a strategy."""

    captured: list[ContentPiece] = []

    @functools.wraps(format_content_output)
    def _capturing_format_content_output(
        content_json: str, strategy_id: str, campaign_id: str, company_id: str
    ) -> str:
        result = format_content_output(content_json, strategy_id, campaign_id, company_id)
        try:
            data = json.loads(result)
            for row in data.get("pieces", []):
                try:
                    captured.append(ContentPiece(**row))
                except Exception:
                    pass
        except Exception:
            pass
        return result

    if not settings.gemini_api_key_set:
        raise EnvironmentError("OPENROUTER_API_KEY is not set.")

    sid = session_id or f"production-{strategy.id}-{uuid.uuid4().hex[:8]}"

    prompt = (
        f"Produce a **{CONTENT_TYPE_META.get(strategy.content_type.value, {}).get('label', strategy.content_type.value)}** "
        f"for this campaign:\n\n"
        f"**Headline**: {campaign_headline}\n"
        f"**Body Copy**: {campaign_body_copy}\n\n"
        f"Strategy ID: {strategy.id}\n"
        f"Campaign ID: {strategy.campaign_id}\n"
        f"Company ID: {strategy.company_id}\n"
    )
    message = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])

    log.info(
        "content_production_agent_starting",
        strategy_id=strategy.id,
        content_type=strategy.content_type.value,
        company=company_name,
    )
    start_time = time.perf_counter()
    pieces: list[ContentPiece] = []

    bt_input = {
        "strategy_id": strategy.id,
        "campaign_id": strategy.campaign_id,
        "content_type": strategy.content_type.value,
        "company": company_name,
    }

    with TracedRun("content_production", input=bt_input) as bt_span:
        try:
            selected_model = ""
            last_error: Exception | None = None
            model_candidates = _candidate_models(PRODUCTION_MODEL)

            for idx, model_name in enumerate(model_candidates, start=1):
                selected_model = model_name
                session_service = InMemorySessionService()
                agent = Agent(
                    name="content_production_agent",
                    model=model_name,
                    description="Generates full-length, publish-ready content from a content strategy.",
                    instruction=_build_instruction(
                        company_name=company_name,
                        tone=tone,
                        audience=audience,
                        goals=goals,
                        content_type=strategy.content_type.value,
                        target_length=strategy.target_length,
                        tone_direction=strategy.tone_direction,
                        structure_outline=strategy.structure_outline,
                    ),
                    tools=[validate_content_piece, _capturing_format_content_output],
                )
                runner = Runner(agent=agent, app_name="signal", session_service=session_service)
                model_sid = f"{sid}-m{idx}"
                await session_service.create_session(
                    app_name="signal",
                    user_id=strategy.company_id,
                    session_id=model_sid,
                )

                log.info(
                    "content_production_agent_attempt",
                    strategy_id=strategy.id,
                    content_type=strategy.content_type.value,
                    model=model_name,
                    attempt=idx,
                    total_models=len(model_candidates),
                )
                try:
                    async for event in runner.run_async(
                        user_id=strategy.company_id, session_id=model_sid, new_message=message
                    ):
                        if event.is_final_response() and event.content and event.content.parts:
                            text = event.content.parts[0].text or ""
                            text_pieces = _extract_pieces(text, strategy)
                            pieces = text_pieces if text_pieces else captured
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if _is_quota_error(exc) and idx < len(model_candidates):
                        delay_s = min(_retry_delay_seconds(exc), 5.0)
                        log.warning(
                            "content_production_agent_model_quota_exhausted",
                            model=model_name,
                            next_model=model_candidates[idx],
                            delay_s=delay_s,
                            error=str(exc),
                        )
                        if delay_s > 0:
                            await asyncio.sleep(delay_s)
                        continue
                    raise

            if last_error and not pieces and not captured:
                raise last_error

            if not pieces and captured:
                pieces = captured

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            track_agent_run(
                agent_name="content_production",
                items_produced=len(pieces),
                company_id=strategy.company_id,
                latency_ms=elapsed_ms,
                success=len(pieces) > 0,
            )
            log.info(
                "content_production_agent_complete",
                pieces=len(pieces),
                elapsed_ms=elapsed_ms,
                model=selected_model,
            )
            if pieces:
                bt_span.log_output(
                    output={"pieces": [p.to_dict() for p in pieces], "count": len(pieces)},
                    scores={
                        "quality": sum(p.quality_score for p in pieces) / len(pieces),
                    },
                    metadata={"latency_ms": elapsed_ms},
                )
        except asyncio.CancelledError:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            track_agent_run(
                agent_name="content_production",
                items_produced=len(pieces),
                company_id=strategy.company_id,
                latency_ms=elapsed_ms,
                success=False,
            )
            log.warning(
                "content_production_agent_cancelled",
                strategy_id=strategy.id,
                company_id=strategy.company_id,
                elapsed_ms=elapsed_ms,
            )
            raise
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            track_agent_run(
                agent_name="content_production",
                items_produced=0,
                company_id=strategy.company_id,
                latency_ms=elapsed_ms,
                success=False,
            )
            log.error("content_production_agent_error", error=str(exc))
            raise

    if pieces:
        await _attach_media_assets(pieces, strategy, company_name, tone)

    if persist and pieces:
        await _persist_pieces(pieces)

    return ContentProductionResponse(
        strategy_id=strategy.id,
        pieces=pieces,
        latency_ms=elapsed_ms,
        success=len(pieces) > 0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pieces(text: str, strategy: ContentStrategy) -> list[ContentPiece]:
    json_pattern = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", re.MULTILINE)
    candidates = json_pattern.findall(text)
    if not candidates:
        candidates = re.findall(r"(\{[^{}]{100,}\}|\[[^\[\]]{100,}\])", text)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            raw_list = (
                data.get("pieces", data.get("content_pieces", []))
                if isinstance(data, dict)
                else data
            )
            if isinstance(data, dict) and not raw_list:
                raw_list = [data]
            if not isinstance(raw_list, list):
                continue

            result: list[ContentPiece] = []
            for item in raw_list:
                ct = str(item.get("content_type", strategy.content_type.value)).lower()
                if ct not in _VALID_TYPES:
                    ct = strategy.content_type.value
                body = item.get("body", "")
                if isinstance(body, list):
                    body = json.dumps(body, indent=2)
                body = str(body)
                result.append(
                    ContentPiece(
                        strategy_id=strategy.id,
                        campaign_id=strategy.campaign_id,
                        company_id=strategy.company_id,
                        content_type=ContentType(ct),
                        title=str(item.get("title", "")),
                        body=body,
                        summary=str(item.get("summary", "")),
                        word_count=len(body.split()),
                        visual_prompt=item.get("visual_prompt"),
                        quality_score=float(item.get("quality_score", 0.7)),
                        brand_alignment=float(item.get("brand_alignment", 0.7)),
                    )
                )
            if result:
                return result
        except (json.JSONDecodeError, TypeError):
            continue
    return []


async def _attach_media_assets(
    pieces: list[ContentPiece],
    strategy: ContentStrategy,
    company_name: str,
    tone: str,
) -> None:
    """Generate Gemini image/video assets when the strategy calls for visuals."""
    if not settings.ENABLE_GEMINI_MEDIA:
        return

    need_visuals = bool(strategy.visual_needed)
    if not need_visuals and not any(p.visual_prompt for p in pieces):
        return

    for piece in pieces:
        if piece.visual_asset_url:
            continue
        prompt = piece.visual_prompt or (
            f"Create a visual for {company_name or 'the brand'} content titled '{piece.title}'. "
            f"Tone: {tone or 'professional'}. "
            f"Format: {piece.content_type.value}. "
            f"Summary: {piece.summary or piece.body[:240]}."
        )
        piece.visual_prompt = prompt

        if piece.content_type == ContentType.VIDEO_SCRIPT and settings.ENABLE_VIDEO_GEN:
            asset = await generate_video_asset(
                prompt=prompt,
                duration_s=8,
                aspect_ratio="16:9",
                style_hint=tone,
            )
        else:
            asset = await generate_image_asset(
                prompt=prompt,
                aspect_ratio="16:9",
                style_hint=tone,
            )
        if asset:
            piece.visual_asset_url = asset.asset_url


async def _persist_pieces(pieces: list[ContentPiece]) -> None:
    db_path = _db_module.DB_PATH
    await _db_module.init_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        for piece in pieces:
            row = piece.to_db_row()
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
                row,
            )
        await db.commit()
    log.info("content_pieces_persisted", count=len(pieces))


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from backend.models.content import ContentStrategy, ContentType

    async def _main() -> None:
        print(f"\n{'=' * 60}")
        print("  SIGNAL — Content Production Agent (Agent 7)")
        print(f"{'=' * 60}\n")

        sample_strategy = ContentStrategy(
            campaign_id="test-campaign-001",
            company_id="test-company-001",
            content_type=ContentType.TWEET_THREAD,
            reasoning="Twitter thread is ideal for this tech audience — high shareability.",
            target_length="5-tweet thread",
            tone_direction="Bold, slightly provocative, data-backed",
            structure_outline=[
                "Hook tweet with bold claim",
                "The data behind the trend",
                "What this means for developers",
                "How NovaTech fits in",
                "CTA tweet",
            ],
            priority_score=0.88,
        )

        response = await run_content_production_agent(
            strategy=sample_strategy,
            campaign_headline="AI Coding Tools Won't Replace You — They'll Make You Dangerous",
            campaign_body_copy="As prediction markets signal rising confidence in AI augmentation over replacement...",
            company_name="NovaTech",
            tone="bold, technical, slightly witty",
            audience="software engineers and CTOs",
            goals="drive developer sign-ups and community growth",
            persist=False,
        )

        if not response.pieces:
            print("No content generated. Check OPENROUTER_API_KEY.")
            return

        print(f"Generated {len(response.pieces)} piece(s) in {response.latency_ms}ms\n")
        for i, p in enumerate(response.pieces, 1):
            print(f"Piece {i}: {p.title}")
            print(f"  Type    : {p.content_type.value}")
            print(f"  Words   : {p.word_count}")
            print(f"  Quality : {p.quality_score:.0%}")
            print(f"  Preview : {p.body[:200]}...")
            print()

    asyncio.run(_main())

