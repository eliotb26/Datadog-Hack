"""Agent 2 — Trend Intelligence Agent.

Continuously polls Polymarket prediction markets and surfaces the most
actionable trend signals for a given company profile.

Architecture:
  - google-adk `Agent` with three tool functions
  - Gemini 2.5 Pro for reasoning-heavy relevance analysis
  - Polymarket Gamma API as the live data source (no auth required)
  - Datadog metrics emitted on every run
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

import backend.database as db_module
from backend.integrations.braintrust_tracing import TracedRun
from backend.integrations.datadog_metrics import track_api_call, track_trend_agent_run
from backend.integrations.polymarket import PolymarketClient
from backend.models.company import CompanyProfile
from backend.models.signal import TrendSignal

from pathlib import Path as _Path

# Walk up from this file to find .env at any ancestor directory
_here = _Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break
else:
    load_dotenv()  # fallback: CWD

log = structlog.get_logger(__name__)

# Gemini model for Agent 2.
# Production: gemini-2.5-pro  |  Dev/free-tier: gemini-2.0-flash
TREND_AGENT_MODEL = os.getenv("GEMINI_MODEL", os.getenv("TREND_AGENT_MODEL", "gemini-3-flash-preview"))
DEFAULT_VOLUME_THRESHOLD = float(os.getenv("POLYMARKET_VOLUME_THRESHOLD", "10000"))
DEFAULT_VOLUME_VELOCITY_THRESHOLD = float(os.getenv("POLYMARKET_VOLUME_VELOCITY_THRESHOLD", "0.0"))


# ──────────────────────────────────────────────────────────────────────────────
# Tool functions (called by the ADK agent's LLM)
# ──────────────────────────────────────────────────────────────────────────────


async def fetch_polymarket_signals(
    volume_threshold: float = DEFAULT_VOLUME_THRESHOLD,
    volume_velocity_threshold: float = DEFAULT_VOLUME_VELOCITY_THRESHOLD,
    limit: int = 50,
) -> str:
    """Fetch high-momentum prediction markets from the Polymarket Gamma API.

    Args:
        volume_threshold: Minimum total trading volume (USD) to include a market.
        volume_velocity_threshold: Minimum 24h/total volume ratio to include a market.
        limit: Maximum number of markets to fetch from the API before filtering.

    Returns:
        JSON string — a list of market objects with fields:
        id, question, category, probability, volume, volume_velocity,
        probability_momentum.
    """
    start = time.perf_counter()
    try:
        async with PolymarketClient(
            volume_threshold=volume_threshold,
            volume_velocity_threshold=volume_velocity_threshold,
        ) as client:
            markets = await client.fetch_top_signals(
                limit=limit,
                top_n=20,
                volume_threshold=volume_threshold,
                volume_velocity_threshold=volume_velocity_threshold,
            )
        latency_ms = (time.perf_counter() - start) * 1000
        track_api_call("polymarket", success=True, latency_ms=latency_ms)

        # Slim down payload so LLM context stays manageable
        slim = [
            {
                "id": m.get("id", ""),
                "title": m.get("question", m.get("title", "")),
                "category": m.get("category", "general"),
                "probability": round(m.get("probability", 0.5), 3),
                "volume": round(m.get("volume", 0), 0),
                "volume_velocity": round(m.get("volume_velocity", 0), 4),
                "probability_momentum": round(m.get("probability_momentum", 0), 4),
            }
            for m in markets
        ]
        log.info("polymarket_tool_result", count=len(slim))
        return json.dumps(slim, indent=2)
    except Exception as exc:  # noqa: BLE001
        track_api_call("polymarket", success=False)
        log.error("polymarket_tool_error", error=str(exc))
        # Keep return shape consistent for tool consumers: always a list JSON payload.
        return json.dumps([])


def score_signal_relevance(
    market_title: str,
    market_category: str,
    company_name: str,
    industry: str,
    target_audience: str,
    campaign_goals: str,
) -> str:
    """Score how relevant a Polymarket signal is to a company's content strategy.

    This is a heuristic helper; the LLM agent is expected to provide the
    final reasoning, but this function gives a quick keyword-based pre-score
    that the agent can use or override.

    Args:
        market_title: The question text of the prediction market.
        market_category: Category tag from Polymarket (e.g. 'crypto', 'politics').
        company_name: Name of the company.
        industry: Industry the company operates in.
        target_audience: The company's primary audience description.
        campaign_goals: What the company wants to achieve with content.

    Returns:
        JSON with fields: pre_score (0.0-1.0), matched_keywords, reasoning_hint.
    """
    title_lower = market_title.lower()
    category_lower = (market_category or "").lower()
    company_lower = (company_name or "").lower()
    audience_lower = (target_audience or "").lower()
    goals_lower = (campaign_goals or "").lower()
    industry_lower = (industry or "").lower()

    # Simple keyword matching to seed the LLM's reasoning
    keyword_pools = {
        "tech": ["ai", "crypto", "software", "tech", "startup", "digital", "cloud", "data"],
        "finance": ["interest rate", "fed", "inflation", "stock", "market", "economy", "bitcoin"],
        "consumer": ["brand", "retail", "consumer", "shopping", "product", "launch"],
        "health": ["fda", "drug", "health", "pharma", "medical", "vaccine", "clinical"],
        "macro": ["election", "policy", "regulation", "law", "government", "trade"],
    }

    matched: List[str] = []
    score = 0.0

    for kw_category, keywords in keyword_pools.items():
        hits = [kw for kw in keywords if kw in title_lower]
        if hits:
            matched.extend(hits)
            # Higher score if industry or goals overlap with this category
            if kw_category in industry_lower or kw_category in goals_lower:
                score += 0.3
            else:
                score += 0.1
        if category_lower and kw_category in category_lower:
            score += 0.15

    # Audience-specific boost
    if any(kw in title_lower for kw in audience_lower.split()):
        score += 0.2
    # Brand mention can indicate directly relevant discourse.
    if company_lower and company_lower in title_lower:
        score += 0.2

    pre_score = min(round(score, 2), 1.0)

    return json.dumps(
        {
            "pre_score": pre_score,
            "matched_keywords": matched[:8],
            "reasoning_hint": (
                f"This market is about '{market_title[:80]}'. "
                f"For a {industry} company targeting {target_audience}, "
                f"assess whether this trend creates content opportunities."
            ),
        }
    )


def format_trend_signals(signals_json: str, company_id: str) -> str:
    """Validate and normalise LLM-generated signals into TrendSignal JSON schema.

    Args:
        signals_json: JSON string — list of signal dicts from the LLM's analysis.
        company_id: ID of the company these signals were scored for.

    Returns:
        JSON string of validated TrendSignal objects ready for persistence.
    """
    try:
        raw = json.loads(signals_json)
        if isinstance(raw, dict) and "signals" in raw:
            raw = raw["signals"]
        if not isinstance(raw, list):
            raw = [raw]
    except (json.JSONDecodeError, TypeError) as exc:
        return json.dumps({"error": f"JSON parse failed: {exc}"})

    validated: List[Dict[str, Any]] = []
    for item in raw:
        try:
            signal = TrendSignal(
                id=str(uuid.uuid4()),
                polymarket_market_id=str(item.get("market_id", item.get("id", "unknown"))),
                title=str(item.get("title", item.get("question", "Untitled"))),
                category=item.get("category"),
                probability=float(item.get("probability", 0.5)),
                probability_momentum=float(item.get("probability_momentum", 0.0)),
                volume=float(item.get("volume", 0.0)),
                volume_velocity=float(item.get("volume_velocity", 0.0)),
                relevance_scores={company_id: float(item.get("relevance_score", 0.0))},
                confidence_score=float(item.get("confidence_score", item.get("relevance_score", 0.0))),
            )
            validated.append(signal.to_dict())
        except Exception as exc:  # noqa: BLE001
            log.warning("signal_validation_failed", item=item, error=str(exc))
            continue

    return json.dumps({"signals": validated, "count": len(validated)}, indent=2, default=str)


# ──────────────────────────────────────────────────────────────────────────────
# Agent definition
# ──────────────────────────────────────────────────────────────────────────────

TREND_AGENT_INSTRUCTION = """You are SIGNAL's Trend Intelligence Agent — a sharp analyst that monitors
Polymarket prediction markets and surfaces actionable content opportunities.

## Your job in each cycle:
1. Call `fetch_polymarket_signals` to get fresh market data.
2. Analyse EACH market for relevance to the company profile provided in the conversation.
3. Call `score_signal_relevance` for markets you consider promising (top 8-10 candidates).
4. Select the best 3-5 signals and call `format_trend_signals` with your final picks.

## Scoring criteria:
- **Volume velocity** (>0.1 = active market, >0.3 = viral): high weight
- **Probability momentum** (rapid movement = interesting story): high weight
- **Relevance** to company's industry, audience, and campaign goals: highest weight
- Prefer markets where the company can take a clear content position

## Output format for `format_trend_signals`:
Pass a JSON list where each item has:
{
  "market_id": "<polymarket id>",
  "title": "<market question>",
  "category": "<category>",
  "probability": <float 0-1>,
  "probability_momentum": <float>,
  "volume": <float>,
  "volume_velocity": <float>,
  "relevance_score": <float 0-1>,
  "confidence_score": <float 0-1>,
  "content_angle": "<one sentence on how the company should use this signal>"
}

## Rules:
- Always call `format_trend_signals` as your last action.
- Return exactly 3-5 signals. Quality over quantity.
- If no markets meet a 0.3 relevance threshold, return the best 3 and note low relevance.
"""

_trend_agent = Agent(
    name="trend_intelligence",
    model=TREND_AGENT_MODEL,
    instruction=TREND_AGENT_INSTRUCTION,
    tools=[fetch_polymarket_signals, score_signal_relevance, format_trend_signals],
)


# ──────────────────────────────────────────────────────────────────────────────
# Public runner function
# ──────────────────────────────────────────────────────────────────────────────


async def run_trend_agent(
    company: CompanyProfile,
    volume_threshold: float = DEFAULT_VOLUME_THRESHOLD,
    volume_velocity_threshold: float = DEFAULT_VOLUME_VELOCITY_THRESHOLD,
    top_n: int = 5,
) -> List[TrendSignal]:
    """Run one full Trend Intelligence Agent cycle for a given company.

    Args:
        company: The CompanyProfile to score signals against.
        volume_threshold: Minimum Polymarket volume to consider a signal.
        top_n: Maximum number of TrendSignal objects to return.

    Returns:
        List of TrendSignal objects ranked by composite score.
    """
    session_service = InMemorySessionService()
    runner = Runner(
        agent=_trend_agent,
        app_name="signal",
        session_service=session_service,
    )

    session_id = f"trend-{company.id}-{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name="signal",
        user_id=company.id,
        session_id=session_id,
    )

    prompt = (
        f"Analyse Polymarket markets for the following company and surface the top trend signals.\n\n"
        f"{company.to_prompt_context()}\n\n"
        f"Volume threshold: ${volume_threshold:,.0f}\n"
        f"Volume velocity threshold: {volume_velocity_threshold:.2f}\n"
        f"Return top {top_n} signals."
    )

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=prompt)],
    )

    bt_input = {
        "company_id": company.id,
        "company_name": company.name,
        "industry": company.industry,
        "volume_threshold": volume_threshold,
        "volume_velocity_threshold": volume_velocity_threshold,
        "top_n": top_n,
    }

    start_time = time.perf_counter()
    signals: List[TrendSignal] = []

    log.info("trend_agent_starting", company=company.name, session_id=session_id)

    with TracedRun("trend_intel", input=bt_input) as bt_span:
        try:
            async for event in runner.run_async(
                user_id=company.id,
                session_id=session_id,
                new_message=message,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_text = event.content.parts[0].text or ""
                    log.debug("trend_agent_final_response", preview=final_text[:200])

                    # Try to parse any embedded JSON from the final response
                    signals = _extract_signals_from_response(final_text, company.id)

            if not signals:
                signals = await _fallback_signals_from_polymarket(
                    company=company,
                    volume_threshold=volume_threshold,
                    volume_velocity_threshold=volume_velocity_threshold,
                    top_n=top_n,
                )
                log.warning(
                    "trend_agent_empty_response_fallback",
                    company=company.name,
                    signals_found=len(signals),
                )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            track_trend_agent_run(
                signals_returned=len(signals),
                company_id=company.id,
                latency_ms=elapsed_ms,
                success=True,
            )
            log.info(
                "trend_agent_complete",
                company=company.name,
                signals_found=len(signals),
                elapsed_ms=round(elapsed_ms, 0),
            )

            bt_span.log_output(
                output={
                    "signals": [s.model_dump(mode="json") for s in signals],
                    "count": len(signals),
                },
                scores={"signals_returned": min(1.0, len(signals) / max(1, top_n))},
                metadata={"latency_ms": elapsed_ms},
            )

        except asyncio.CancelledError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            track_trend_agent_run(
                signals_returned=len(signals),
                company_id=company.id,
                latency_ms=elapsed_ms,
                success=False,
            )
            log.warning(
                "trend_agent_cancelled",
                company=company.name,
                session_id=session_id,
                elapsed_ms=round(elapsed_ms, 0),
            )
            raise
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            track_trend_agent_run(
                signals_returned=0,
                company_id=company.id,
                latency_ms=elapsed_ms,
                success=False,
            )
            log.error("trend_agent_error", company=company.name, error=str(exc))
            signals = await _fallback_signals_from_polymarket(
                company=company,
                volume_threshold=volume_threshold,
                volume_velocity_threshold=volume_velocity_threshold,
                top_n=top_n,
            )
            if not signals:
                raise
            log.warning(
                "trend_agent_fallback_used",
                company=company.name,
                signals_found=len(signals),
            )

    # Enforce threshold in code (not only via prompt guidance).
    signals = [
        s
        for s in signals
        if s.volume >= volume_threshold and s.volume_velocity >= volume_velocity_threshold
    ]
    # Apply feedback-loop calibration before final ranking.
    signals = await _apply_feedback_calibration(company, signals)
    signals.sort(key=lambda s: s.composite_score(company.id), reverse=True)
    return signals[:top_n]


async def _fallback_signals_from_polymarket(
    company: CompanyProfile,
    volume_threshold: float,
    volume_velocity_threshold: float,
    top_n: int,
) -> List[TrendSignal]:
    """Return direct Polymarket-ranked signals when LLM orchestration fails."""
    try:
        async with PolymarketClient(
            volume_threshold=volume_threshold,
            volume_velocity_threshold=volume_velocity_threshold,
        ) as client:
            markets = await client.fetch_top_signals(
                limit=max(25, top_n * 5),
                top_n=top_n,
                volume_threshold=volume_threshold,
                volume_velocity_threshold=volume_velocity_threshold,
            )
    except Exception as exc:  # noqa: BLE001
        log.error("trend_agent_fallback_failed", error=str(exc))
        return []

    signals: List[TrendSignal] = []
    for m in markets:
        title = str(m.get("question", m.get("title", ""))).strip()
        if not title:
            continue
        category = str(m.get("category") or "general").strip().lower()

        relevance_score = 0.0
        try:
            relevance_raw = score_signal_relevance(
                market_title=title,
                market_category=category,
                company_name=company.name,
                industry=company.industry,
                target_audience=company.target_audience or "",
                campaign_goals=company.campaign_goals or "",
            )
            relevance_score = float(json.loads(relevance_raw).get("pre_score", 0.0))
        except Exception:
            relevance_score = 0.0

        signals.append(
            TrendSignal(
                polymarket_market_id=str(m.get("id", "")),
                title=title,
                category=category,
                probability=float(m.get("probability", 0.5)),
                probability_momentum=float(m.get("probability_momentum", 0.0)),
                volume=float(m.get("volume", 0.0)),
                volume_velocity=float(m.get("volume_velocity", 0.0)),
                relevance_scores={company.id: relevance_score},
                confidence_score=relevance_score,
            )
        )

    return signals[:top_n]


async def _apply_feedback_calibration(
    company: CompanyProfile,
    signals: List[TrendSignal],
) -> List[TrendSignal]:
    """Apply Loop 3 calibration multipliers and Loop 2 relevance hints."""
    if not signals:
        return signals

    cal_rows = await db_module.get_signal_calibration(
        company_type=company.industry,
        min_accuracy=0.30,
        limit=200,
    )
    if not cal_rows:
        cal_rows = await db_module.get_signal_calibration(
            min_accuracy=0.30,
            limit=200,
        )

    best_by_category: Dict[str, Dict[str, Any]] = {}
    for row in cal_rows:
        category = str(row.get("signal_category") or "unknown").lower()
        prev = best_by_category.get(category)
        if not prev or float(row.get("accuracy_score") or 0.0) > float(prev.get("accuracy_score") or 0.0):
            best_by_category[category] = row

    pattern_rows = await db_module.get_shared_patterns(
        industry=company.industry,
        min_confidence=0.60,
        limit=20,
    )
    category_keywords: Dict[str, float] = {}
    for row in pattern_rows:
        desc = str(row.get("description", "")).lower()
        conf = float(row.get("confidence") or 0.0)
        for sig in signals:
            cat = str(sig.category or "unknown").lower()
            if cat and cat in desc:
                category_keywords[cat] = max(category_keywords.get(cat, 0.0), conf)

    for sig in signals:
        category = str(sig.category or "unknown").lower()
        relevance = float(sig.relevance_scores.get(company.id, 0.0))

        cal = best_by_category.get(category)
        if cal:
            predicted = float(cal.get("predicted_engagement") or 0.0)
            actual = float(cal.get("actual_engagement") or 0.0)
            accuracy = float(cal.get("accuracy_score") or 0.0)
            ratio = (actual / predicted) if predicted > 0 else 1.0
            multiplier = max(0.6, min(1.4, ratio * (0.75 + 0.5 * accuracy)))
            relevance *= multiplier

        conf_hint = category_keywords.get(category, 0.0)
        if conf_hint > 0:
            relevance *= 1.0 + min(0.15, conf_hint * 0.2)

        sig.relevance_scores[company.id] = round(max(0.0, min(1.0, relevance)), 4)

    return signals


def _extract_signals_from_response(text: str, company_id: str) -> List[TrendSignal]:
    """Parse TrendSignal objects out of the agent's final text response."""
    # The format_trend_signals tool already validated and returned JSON;
    # the LLM may echo it in its final message or it may be in a code block.
    import re

    # Try extracting JSON blocks
    json_pattern = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", re.MULTILINE)
    candidates = json_pattern.findall(text)
    if not candidates:
        # Fallback: look for raw JSON objects/arrays
        candidates = re.findall(r'(\{[^{}]{50,}\}|\[[^\[\]]{50,}\])', text)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            raw_list = data.get("signals", data) if isinstance(data, dict) else data
            if not isinstance(raw_list, list):
                continue
            result = []
            for item in raw_list:
                try:
                    sig = TrendSignal(
                        polymarket_market_id=str(item.get("market_id", item.get("id", ""))),
                        title=str(item.get("title", "")),
                        category=item.get("category"),
                        probability=float(item.get("probability", 0.5)),
                        probability_momentum=float(item.get("probability_momentum", 0.0)),
                        volume=float(item.get("volume", 0.0)),
                        volume_velocity=float(item.get("volume_velocity", 0.0)),
                        relevance_scores={company_id: float(item.get("relevance_score", 0.0))},
                        confidence_score=float(item.get("confidence_score", 0.0)),
                    )
                    result.append(sig)
                except Exception:  # noqa: BLE001
                    continue
            if result:
                return result
        except (json.JSONDecodeError, TypeError):
            continue

    return []


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry-point for quick manual testing
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Agent 2 — Trend Intelligence Agent")
    parser.add_argument("--company", default="TechCorp", help="Company name")
    parser.add_argument("--industry", default="SaaS / Developer Tools", help="Industry")
    parser.add_argument("--audience", default="software engineers and CTOs", help="Target audience")
    parser.add_argument("--goals", default="grow developer community and drive sign-ups", help="Campaign goals")
    parser.add_argument("--threshold", type=float, default=5000.0, help="Volume threshold")
    parser.add_argument("--top", type=int, default=5, help="Number of signals to return")
    args = parser.parse_args()

    sample_company = CompanyProfile(
        name=args.company,
        industry=args.industry,
        target_audience=args.audience,
        campaign_goals=args.goals,
        tone_of_voice="technical, authoritative, slightly witty",
    )

    async def _main() -> None:
        print(f"\n{'='*60}")
        print(f"  SIGNAL — Trend Intelligence Agent")
        print(f"  Company: {sample_company.name} ({sample_company.industry})")
        print(f"{'='*60}\n")

        signals = await run_trend_agent(
            company=sample_company,
            volume_threshold=args.threshold,
            top_n=args.top,
        )

        if not signals:
            print("No signals returned. Check GEMINI_API_KEY and Polymarket connectivity.")
            return

        print(f"✓ {len(signals)} trend signal(s) surfaced:\n")
        for i, sig in enumerate(signals, 1):
            relevance = sig.relevance_scores.get(sample_company.id, 0.0)
            print(f"  [{i}] {sig.title}")
            print(f"      Category: {sig.category or 'N/A'} | Probability: {sig.probability:.1%}")
            print(f"      Volume: ${sig.volume:,.0f} | Velocity: {sig.volume_velocity:.2%}/day")
            print(f"      Relevance: {relevance:.0%} | Confidence: {sig.confidence_score:.0%}")
            print()

    asyncio.run(_main())
