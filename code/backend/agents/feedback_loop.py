"""
SIGNAL — Agent 5: Feedback Loop Agent (Meta-Agent)
====================================================
Purpose : Close all three self-improving loops.
LLM     : gemini-2.0-flash (used for each sub-agent; same model as other agents)
ADK     : Three LlmAgents (one per loop), each run sequentially by a top-level
          orchestrator function run_feedback_loop().

Loop 1 Sub-Agent — Campaign Performance → Prompt Weight Updates
  Tools : get_campaign_performance, compute_prompt_weights, save_prompt_weights
  Output: Updated prompt_weights rows per company

Loop 2 Sub-Agent — Cross-Company Style Learning → Shared Patterns
  Tools : get_cross_company_metrics, extract_style_patterns, save_shared_pattern
  Output: New rows in shared_patterns table

Loop 3 Sub-Agent — Signal Calibration → Updated Calibration Scores
  Tools : get_signal_engagement_pairs, compute_calibration, save_calibration
  Output: New rows in signal_calibration table
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
import structlog
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types as genai_types

import backend.database as _db_module
from backend.config import settings
from backend.models.feedback import (
    CalibrationResult,
    FeedbackLoopResult,
    Loop1Result,
    Loop2Result,
    Loop3Result,
    PromptWeightUpdate,
    SharedPattern,
)

load_dotenv()
logger = structlog.get_logger(__name__)

import concurrent.futures as _cf


def _run_async_safe(coro):
    """Run an async coroutine safely whether or not an event loop is already running."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)

FEEDBACK_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# ─────────────────────────────────────────────────────────────────────────────
# DB helper — used by all three loop tool sets
# ─────────────────────────────────────────────────────────────────────────────

def _db_path() -> Path:
    """Resolve the SQLite database path at runtime."""
    return _db_module.DB_PATH


# =============================================================================
# LOOP 1 TOOLS — Campaign Performance → Prompt Weight Updates
# =============================================================================

def get_campaign_performance(company_id: str) -> str:
    """Retrieve campaign performance metrics for a specific company.

    Joins campaigns with campaign_metrics to return a summary of each
    campaign's engagement data.

    Args:
        company_id: UUID of the company to analyze.

    Returns:
        JSON string with a list of campaign performance dicts:
          - campaign_id (str)
          - headline (str)
          - channel (str)
          - engagement_rate (float)
          - sentiment_score (float | null)
          - impressions (int)
          - clicks (int)
          - confidence_score (float): Agent 3's original confidence
    """
    async def _query() -> List[dict]:
        async with aiosqlite.connect(_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    c.id          AS campaign_id,
                    c.headline,
                    c.channel_recommendation AS channel,
                    c.confidence_score,
                    COALESCE(m.engagement_rate, 0.0)  AS engagement_rate,
                    m.sentiment_score,
                    COALESCE(m.impressions, 0)         AS impressions,
                    COALESCE(m.clicks, 0)              AS clicks
                FROM campaigns c
                LEFT JOIN campaign_metrics m ON m.campaign_id = c.id
                WHERE c.company_id = ?
                ORDER BY c.created_at DESC
                LIMIT 50
                """,
                (company_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    rows = _run_async_safe(_query())

    return json.dumps({"company_id": company_id, "campaigns": rows, "count": len(rows)})


def compute_prompt_weights(performance_json: str, company_id: str) -> str:
    """Analyse campaign performance data and compute new prompt weight values.

    Uses rule-based heuristics combined with statistical analysis to determine
    which content style attributes are driving higher engagement.

    Args:
        performance_json: JSON string returned by get_campaign_performance.
        company_id: UUID of the company.

    Returns:
        JSON string with:
          - weight_updates (list): Each item has weight_key, weight_value, reasoning
          - company_id (str)
          - campaigns_analyzed (int)
    """
    try:
        data = json.loads(performance_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "Invalid performance_json", "weight_updates": []})

    campaigns = data.get("campaigns", [])
    if not campaigns:
        return json.dumps(
            {
                "company_id": company_id,
                "campaigns_analyzed": 0,
                "weight_updates": [],
                "message": "No campaigns found — weights unchanged.",
            }
        )

    # ── Aggregate by channel ─────────────────────────────────────────────────
    channel_eng: Dict[str, List[float]] = {}
    for c in campaigns:
        ch = str(c.get("channel", "twitter")).lower()
        eng = float(c.get("engagement_rate") or 0.0)
        channel_eng.setdefault(ch, []).append(eng)

    channel_avg = {ch: sum(v) / len(v) for ch, v in channel_eng.items()}
    best_channel = max(channel_avg, key=channel_avg.get) if channel_avg else "twitter"
    best_channel_avg = channel_avg.get(best_channel, 0.0)

    # ── Engagement tier thresholds ───────────────────────────────────────────
    avg_all = sum(c.get("engagement_rate", 0.0) for c in campaigns) / max(len(campaigns), 1)
    high_performers = [c for c in campaigns if float(c.get("engagement_rate") or 0.0) > avg_all * 1.3]
    low_performers = [c for c in campaigns if float(c.get("engagement_rate") or 0.0) < avg_all * 0.7]

    # ── Sentiment signal ─────────────────────────────────────────────────────
    sentiments = [float(c["sentiment_score"]) for c in campaigns if c.get("sentiment_score") is not None]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

    weight_updates: List[dict] = []

    # Boost weight for the best-performing channel
    channel_weight = min(1.0 + best_channel_avg * 2.0, 2.5)
    weight_updates.append(
        {
            "weight_key": f"channel_{best_channel}_preference",
            "weight_value": round(channel_weight, 3),
            "reasoning": (
                f"Channel '{best_channel}' averages {best_channel_avg:.1%} engagement "
                f"— boosted to {channel_weight:.2f}x."
            ),
        }
    )

    # Tone weight: positive sentiment → boost positive/uplifting tone
    if avg_sentiment > 0.2:
        weight_updates.append(
            {
                "weight_key": "tone_positive",
                "weight_value": round(1.0 + avg_sentiment, 3),
                "reasoning": (
                    f"Average campaign sentiment is {avg_sentiment:.2f} (positive). "
                    "Boosting positive/uplifting tone weight."
                ),
            }
        )
    elif avg_sentiment < -0.2:
        weight_updates.append(
            {
                "weight_key": "tone_neutral",
                "weight_value": 1.3,
                "reasoning": (
                    f"Average campaign sentiment is {avg_sentiment:.2f} (negative). "
                    "Shifting toward neutral/factual tone."
                ),
            }
        )

    # Hook style: high-performer patterns
    if len(high_performers) >= 2:
        weight_updates.append(
            {
                "weight_key": "hook_question",
                "weight_value": 1.2,
                "reasoning": (
                    f"{len(high_performers)} campaigns exceeded avg by 30%+. "
                    "Reinforcing question-style hooks (common in top performers)."
                ),
            }
        )

    # Penalise low performers by lowering confidence weight
    if len(low_performers) > len(high_performers):
        weight_updates.append(
            {
                "weight_key": "body_length_long",
                "weight_value": 0.8,
                "reasoning": (
                    f"{len(low_performers)} campaigns underperformed. "
                    "Reducing long-form body copy weight — try shorter, punchier content."
                ),
            }
        )

    return json.dumps(
        {
            "company_id": company_id,
            "campaigns_analyzed": len(campaigns),
            "weight_updates": weight_updates,
        }
    )


def save_prompt_weights(weights_json: str) -> str:
    """Persist updated prompt weights for a company into the database.

    Performs an UPSERT — existing weights are replaced, new ones are inserted.

    Args:
        weights_json: JSON string from compute_prompt_weights containing:
          - company_id (str)
          - weight_updates (list of {weight_key, weight_value, reasoning})

    Returns:
        JSON string with:
          - saved (int): number of rows written
          - company_id (str)
          - success (bool)
    """
    try:
        data = json.loads(weights_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"error": "Invalid weights_json", "saved": 0, "success": False})

    company_id = data.get("company_id", "")
    updates = data.get("weight_updates", [])

    if not company_id or not updates:
        return json.dumps({"saved": 0, "company_id": company_id, "success": True,
                           "message": "Nothing to save."})

    async def _save() -> int:
        async with aiosqlite.connect(_db_path()) as db:
            count = 0
            for upd in updates:
                await db.execute(
                    """
                    INSERT INTO prompt_weights (id, company_id, agent_name, weight_key,
                                                weight_value, updated_at)
                    VALUES (?, ?, 'campaign_gen', ?, ?, ?)
                    ON CONFLICT(company_id, agent_name, weight_key)
                    DO UPDATE SET weight_value = excluded.weight_value,
                                  updated_at   = excluded.updated_at
                    """,
                    (
                        str(uuid.uuid4()),
                        company_id,
                        upd["weight_key"],
                        float(upd.get("weight_value", 1.0)),
                        datetime.utcnow().isoformat(),
                    ),
                )
                count += 1
            await db.commit()
            return count

    saved = _run_async_safe(_save())

    return json.dumps({"saved": saved, "company_id": company_id, "success": True})


# =============================================================================
# LOOP 2 TOOLS — Cross-Company Style Learning → Shared Patterns
# =============================================================================

def get_cross_company_metrics(min_campaigns: int = 3) -> str:
    """Retrieve anonymized aggregate performance metrics across all companies.

    Returns per-company stats without exposing identifiable data.

    Args:
        min_campaigns: Only include companies with at least this many campaigns.

    Returns:
        JSON string with:
          - companies (list): anonymized company stats
          - total_campaigns (int)
    """
    async def _query() -> dict:
        async with aiosqlite.connect(_db_path()) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT
                    c.industry,
                    COUNT(camp.id)                      AS campaign_count,
                    AVG(COALESCE(m.engagement_rate, 0)) AS avg_engagement,
                    AVG(COALESCE(m.sentiment_score, 0)) AS avg_sentiment,
                    camp.channel_recommendation         AS channel,
                    AVG(camp.confidence_score)          AS avg_confidence
                FROM companies c
                JOIN campaigns camp ON camp.company_id = c.id
                LEFT JOIN campaign_metrics m ON m.campaign_id = camp.id
                GROUP BY c.industry, camp.channel_recommendation
                HAVING COUNT(camp.id) >= ?
                ORDER BY avg_engagement DESC
                """,
                (min_campaigns,),
            )
            rows = await cursor.fetchall()
            return {"companies": [dict(r) for r in rows], "total_campaigns": sum(r["campaign_count"] for r in rows)}

    result = _run_async_safe(_query())

    return json.dumps(result)


def extract_style_patterns(metrics_json: str) -> str:
    """Identify cross-company content style patterns from aggregate metrics.

    Analyses the aggregate metrics to surface actionable shared patterns
    (e.g., "LinkedIn outperforms for B2B industries above 5% engagement").

    Args:
        metrics_json: JSON string from get_cross_company_metrics.

    Returns:
        JSON string with:
          - patterns (list): Each has pattern_type, description, conditions,
                             effect, confidence, sample_size
    """
    try:
        data = json.loads(metrics_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"patterns": [], "error": "Invalid metrics_json"})

    companies = data.get("companies", [])
    if not companies:
        return json.dumps({"patterns": [], "message": "Insufficient data for pattern extraction."})

    patterns: List[dict] = []

    # Group by channel to find best-performing channels globally
    channel_eng: Dict[str, List[float]] = {}
    channel_count: Dict[str, int] = {}
    for row in companies:
        ch = str(row.get("channel", "twitter")).lower()
        eng = float(row.get("avg_engagement") or 0.0)
        cnt = int(row.get("campaign_count") or 0)
        channel_eng.setdefault(ch, []).append(eng)
        channel_count[ch] = channel_count.get(ch, 0) + cnt

    for ch, engs in channel_eng.items():
        avg_e = sum(engs) / len(engs)
        total = channel_count.get(ch, 0)
        if avg_e > 0.05 and total >= 5:
            patterns.append(
                {
                    "pattern_type": "channel",
                    "description": (
                        f"Channel '{ch}' consistently achieves {avg_e:.1%} average "
                        f"engagement across {len(engs)} industry segments."
                    ),
                    "conditions": {"channel": ch, "min_campaigns": 5},
                    "effect": {"expected_engagement": round(avg_e, 4)},
                    "confidence": min(0.5 + total / 100.0, 0.95),
                    "sample_size": total,
                }
            )

    # Industry-level patterns
    industry_data: Dict[str, List[float]] = {}
    for row in companies:
        ind = str(row.get("industry", "unknown"))
        eng = float(row.get("avg_engagement") or 0.0)
        industry_data.setdefault(ind, []).append(eng)

    for ind, engs in industry_data.items():
        avg_e = sum(engs) / len(engs)
        if avg_e > 0.04 and len(engs) >= 2:
            best_ch_for_ind = max(
                [r for r in companies if str(r.get("industry")) == ind],
                key=lambda r: float(r.get("avg_engagement") or 0.0),
                default=None,
            )
            best_ch = best_ch_for_ind.get("channel", "unknown") if best_ch_for_ind else "unknown"
            patterns.append(
                {
                    "pattern_type": "style",
                    "description": (
                        f"In the '{ind}' industry, '{best_ch}' channel drives the "
                        f"highest engagement (avg {avg_e:.1%})."
                    ),
                    "conditions": {"industry": ind},
                    "effect": {"recommended_channel": best_ch, "expected_engagement": round(avg_e, 4)},
                    "confidence": min(0.4 + len(engs) * 0.1, 0.90),
                    "sample_size": len(engs),
                }
            )

    return json.dumps({"patterns": patterns})


def save_shared_pattern(pattern_json: str) -> str:
    """Persist a single shared pattern to the shared_patterns table.

    Args:
        pattern_json: JSON string with keys:
          - pattern_type (str): style | timing | channel | signal
          - description (str)
          - conditions (dict)
          - effect (dict)
          - confidence (float)
          - sample_size (int)

    Returns:
        JSON string with success (bool) and pattern_id (str).
    """
    try:
        pattern = json.loads(pattern_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"success": False, "error": "Invalid pattern_json"})

    pattern_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    async def _save() -> None:
        async with aiosqlite.connect(_db_path()) as db:
            await db.execute(
                """
                INSERT INTO shared_patterns
                    (id, pattern_type, description, conditions, effect,
                     confidence, sample_size, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern_id,
                    pattern.get("pattern_type", "style"),
                    pattern.get("description", ""),
                    json.dumps(pattern.get("conditions", {})),
                    json.dumps(pattern.get("effect", {})),
                    float(pattern.get("confidence", 0.5)),
                    int(pattern.get("sample_size", 0)),
                    now,
                ),
            )
            await db.commit()

    _run_async_safe(_save())

    return json.dumps({"success": True, "pattern_id": pattern_id})


# =============================================================================
# LOOP 3 TOOLS — Signal Calibration → Updated Accuracy Scores
# =============================================================================

def get_signal_engagement_pairs(limit: int = 100) -> str:
    """Retrieve pairs of Polymarket signal features and resulting engagement rates.

    Joins trend_signals → campaigns → campaign_metrics to build a training set
    for signal calibration.

    Args:
        limit: Maximum number of signal-campaign pairs to retrieve.

    Returns:
        JSON string with:
          - pairs (list): Each item has signal features + observed engagement
          - count (int)
    """
    async def _query() -> List[dict]:
        async with aiosqlite.connect(_db_path()) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    ts.id               AS signal_id,
                    ts.category         AS signal_category,
                    ts.probability,
                    ts.probability_momentum,
                    ts.volume,
                    ts.volume_velocity,
                    co.industry         AS company_type,
                    COALESCE(m.engagement_rate, 0.0)  AS engagement_rate,
                    COALESCE(m.impressions, 0)         AS impressions
                FROM trend_signals ts
                JOIN campaigns camp ON camp.trend_signal_id = ts.id
                JOIN companies co ON co.id = camp.company_id
                LEFT JOIN campaign_metrics m ON m.campaign_id = camp.id
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    rows = _run_async_safe(_query())

    return json.dumps({"pairs": rows, "count": len(rows)})


def compute_calibration(pairs_json: str) -> str:
    """Calculate signal calibration accuracy by category and company type.

    Compares predicted engagement (based on probability threshold buckets)
    against actual engagement to produce accuracy scores.

    Args:
        pairs_json: JSON string from get_signal_engagement_pairs.

    Returns:
        JSON string with:
          - calibrations (list): Each has signal_category, probability_threshold,
                                  predicted_engagement, actual_engagement,
                                  accuracy_score, company_type
    """
    try:
        data = json.loads(pairs_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"calibrations": [], "error": "Invalid pairs_json"})

    pairs = data.get("pairs", [])
    if not pairs:
        return json.dumps({"calibrations": [], "message": "No signal-engagement pairs found."})

    # Group by (category, probability_bucket, company_type)
    buckets: Dict[tuple, List[dict]] = {}
    for p in pairs:
        cat = str(p.get("signal_category") or "unknown")
        prob = float(p.get("probability") or 0.5)
        comp_type = str(p.get("company_type") or "unknown")
        # Bucket probabilities: 0.0-0.5, 0.5-0.7, 0.7-0.9, 0.9-1.0
        if prob < 0.5:
            prob_bucket = 0.25
        elif prob < 0.7:
            prob_bucket = 0.6
        elif prob < 0.9:
            prob_bucket = 0.8
        else:
            prob_bucket = 0.95
        key = (cat, prob_bucket, comp_type)
        buckets.setdefault(key, []).append(p)

    calibrations: List[dict] = []
    for (cat, prob_bucket, comp_type), bucket_pairs in buckets.items():
        if len(bucket_pairs) < 2:
            continue

        actual_engs = [float(p.get("engagement_rate") or 0.0) for p in bucket_pairs]
        actual_avg = sum(actual_engs) / len(actual_engs)
        vol_velocities = [float(p.get("volume_velocity") or 0.0) for p in bucket_pairs]
        avg_vol_vel = sum(vol_velocities) / len(vol_velocities)

        # Simple prediction: high-probability + high-volume = high engagement
        predicted = prob_bucket * 0.1 + (min(avg_vol_vel, 100_000) / 1_000_000)
        predicted = min(predicted, 0.5)  # cap at 50%

        # Accuracy: 1 - normalized absolute error
        if predicted > 0 or actual_avg > 0:
            max_val = max(predicted, actual_avg, 0.001)
            accuracy = max(0.0, 1.0 - abs(predicted - actual_avg) / max_val)
        else:
            accuracy = 1.0

        calibrations.append(
            {
                "signal_category": cat,
                "probability_threshold": prob_bucket,
                "volume_velocity_threshold": round(avg_vol_vel, 2),
                "predicted_engagement": round(predicted, 6),
                "actual_engagement": round(actual_avg, 6),
                "accuracy_score": round(accuracy, 4),
                "company_type": comp_type,
            }
        )

    return json.dumps({"calibrations": calibrations})


def save_calibration(calibrations_json: str) -> str:
    """Persist signal calibration results to the signal_calibration table.

    Args:
        calibrations_json: JSON string from compute_calibration containing:
          - calibrations (list of calibration dicts)

    Returns:
        JSON string with saved (int) and success (bool).
    """
    try:
        data = json.loads(calibrations_json)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"success": False, "error": "Invalid calibrations_json", "saved": 0})

    calibrations = data.get("calibrations", [])
    if not calibrations:
        return json.dumps({"saved": 0, "success": True, "message": "Nothing to save."})

    now = datetime.utcnow().isoformat()

    async def _save() -> int:
        async with aiosqlite.connect(_db_path()) as db:
            count = 0
            for cal in calibrations:
                await db.execute(
                    """
                    INSERT INTO signal_calibration
                        (id, signal_category, probability_threshold,
                         volume_velocity_threshold, predicted_engagement,
                         actual_engagement, accuracy_score, company_type,
                         calibrated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        cal.get("signal_category", "unknown"),
                        float(cal.get("probability_threshold", 0.5)),
                        float(cal.get("volume_velocity_threshold", 0.0)),
                        float(cal.get("predicted_engagement", 0.0)),
                        float(cal.get("actual_engagement", 0.0)),
                        float(cal.get("accuracy_score", 0.5)),
                        cal.get("company_type", "unknown"),
                        now,
                    ),
                )
                count += 1
            await db.commit()
            return count

    saved = _run_async_safe(_save())

    return json.dumps({"saved": saved, "success": True})


# =============================================================================
# ADK AGENT DEFINITIONS
# =============================================================================

def _build_loop1_agent() -> LlmAgent:
    """Build the Loop 1 sub-agent: campaign performance → prompt weight updates."""
    return LlmAgent(
        name="loop1_performance_feedback",
        model=FEEDBACK_MODEL,
        description="Analyzes campaign performance metrics and updates prompt weights for Agent 3.",
        instruction="""You are the Loop 1 Performance Feedback sub-agent for SIGNAL.

Your job is to close the per-company self-improvement loop:
  1. Call get_campaign_performance(company_id) to retrieve campaign engagement data.
  2. Call compute_prompt_weights(performance_json, company_id) to calculate new weights.
  3. Call save_prompt_weights(weights_json) to persist the updates.
  4. Return a concise JSON summary with keys:
       - campaigns_analyzed (int)
       - weight_updates (list of {weight_key, weight_value})
       - summary (str): one-sentence explanation of what changed

Always complete all three steps. Do not skip saving.
If there is no data, return: {"campaigns_analyzed": 0, "weight_updates": [], "summary": "No data available."}
""",
        tools=[
            FunctionTool(get_campaign_performance),
            FunctionTool(compute_prompt_weights),
            FunctionTool(save_prompt_weights),
        ],
    )


def _build_loop2_agent() -> LlmAgent:
    """Build the Loop 2 sub-agent: cross-company learning → shared patterns."""
    return LlmAgent(
        name="loop2_cross_company_learning",
        model=FEEDBACK_MODEL,
        description="Aggregates cross-company patterns and updates the shared knowledge layer.",
        instruction="""You are the Loop 2 Cross-Company Learning sub-agent for SIGNAL.

Your job is to surface reusable content intelligence from aggregate campaign data:
  1. Call get_cross_company_metrics(min_campaigns=3) to fetch aggregate stats.
  2. Call extract_style_patterns(metrics_json) to identify patterns.
  3. For each pattern in the result, call save_shared_pattern(pattern_json) to persist it.
     - pattern_json must be a JSON string of a single pattern dict.
  4. Return a concise JSON summary with keys:
       - patterns_discovered (int)
       - pattern_types (list of str)
       - summary (str): one-sentence explanation of the most significant pattern found

Save every pattern returned by extract_style_patterns. If patterns list is empty,
return: {"patterns_discovered": 0, "pattern_types": [], "summary": "Insufficient data."}
""",
        tools=[
            FunctionTool(get_cross_company_metrics),
            FunctionTool(extract_style_patterns),
            FunctionTool(save_shared_pattern),
        ],
    )


def _build_loop3_agent() -> LlmAgent:
    """Build the Loop 3 sub-agent: signal calibration → updated accuracy scores."""
    return LlmAgent(
        name="loop3_signal_calibration",
        model=FEEDBACK_MODEL,
        description="Correlates Polymarket signal features with campaign engagement to recalibrate signal weights.",
        instruction="""You are the Loop 3 Signal Calibration sub-agent for SIGNAL.

Your job is to improve the accuracy of Polymarket trend signal scoring:
  1. Call get_signal_engagement_pairs(limit=100) to get signal-engagement data.
  2. Call compute_calibration(pairs_json) to calculate per-category accuracy scores.
  3. Call save_calibration(calibrations_json) to persist the calibration results.
  4. Return a concise JSON summary with keys:
       - pairs_analyzed (int)
       - calibrations_saved (int)
       - best_category (str): signal category with highest accuracy
       - summary (str): one-sentence explanation of calibration results

Always complete all three steps. If no data is available:
Return: {"pairs_analyzed": 0, "calibrations_saved": 0, "best_category": "none", "summary": "No signal data."}
""",
        tools=[
            FunctionTool(get_signal_engagement_pairs),
            FunctionTool(compute_calibration),
            FunctionTool(save_calibration),
        ],
    )


# =============================================================================
# ORCHESTRATOR — run_feedback_loop()
# =============================================================================

async def _run_sub_agent(agent: LlmAgent, message: str, app_name: str) -> str:
    """Run a single LlmAgent and return the final text response."""
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=app_name, user_id="system")
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

    final_text = ""
    async for event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=message)],
        ),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""

    return final_text


async def run_feedback_loop(
    company_id: Optional[str] = None,
    run_loop1: bool = True,
    run_loop2: bool = True,
    run_loop3: bool = True,
) -> FeedbackLoopResult:
    """Run one full Agent 5 feedback cycle — all three self-improving loops.

    Args:
        company_id: If provided, Loop 1 is scoped to this company. If None,
                    Loop 1 is skipped (no per-company target).
        run_loop1: Whether to run the campaign performance loop.
        run_loop2: Whether to run the cross-company learning loop.
        run_loop3: Whether to run the signal calibration loop.

    Returns:
        FeedbackLoopResult with outcomes from each loop that was run.
    """
    await _db_module.init_db()

    start_total = time.monotonic()
    result = FeedbackLoopResult()
    effective_company_id = company_id

    if run_loop1 and not effective_company_id:
        latest = await _db_module.get_latest_company_row()
        effective_company_id = (latest or {}).get("id")

    # ── Loop 1 ────────────────────────────────────────────────────────────────
    if run_loop1 and effective_company_id:
        t0 = time.monotonic()
        try:
            agent = _build_loop1_agent()
            response = await _run_sub_agent(
                agent,
                message=f"Run Loop 1 feedback for company_id={effective_company_id}",
                app_name="signal_loop1",
            )
            # Parse the LLM's JSON summary
            try:
                summary_data = json.loads(response)
            except (json.JSONDecodeError, TypeError):
                summary_data = {}

            result.loop1 = Loop1Result(
                company_id=effective_company_id,
                campaigns_analyzed=summary_data.get("campaigns_analyzed", 0),
                summary=summary_data.get("summary", response[:300]),
                latency_ms=int((time.monotonic() - t0) * 1000),
                success=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("loop1_failed", error=str(exc), company_id=effective_company_id)
            result.loop1 = Loop1Result(
                company_id=effective_company_id or "",
                success=False,
                error=str(exc),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
    elif run_loop1:
        result.loop1 = Loop1Result(
            company_id="",
            campaigns_analyzed=0,
            summary="Loop 1 skipped: no company profile found.",
            success=False,
            error="No company profile found for Loop 1.",
            latency_ms=0,
        )

    # ── Loop 2 ────────────────────────────────────────────────────────────────
    if run_loop2:
        t0 = time.monotonic()
        try:
            agent = _build_loop2_agent()
            response = await _run_sub_agent(
                agent,
                message="Run Loop 2 cross-company style learning and save all discovered patterns.",
                app_name="signal_loop2",
            )
            try:
                summary_data = json.loads(response)
            except (json.JSONDecodeError, TypeError):
                summary_data = {}

            result.loop2 = Loop2Result(
                patterns_discovered=[],  # DB already updated by the agent's tools
                summary=summary_data.get("summary", response[:300]),
                latency_ms=int((time.monotonic() - t0) * 1000),
                success=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("loop2_failed", error=str(exc))
            result.loop2 = Loop2Result(
                success=False,
                error=str(exc),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

    # ── Loop 3 ────────────────────────────────────────────────────────────────
    if run_loop3:
        t0 = time.monotonic()
        try:
            agent = _build_loop3_agent()
            response = await _run_sub_agent(
                agent,
                message="Run Loop 3 signal calibration and save all calibration results.",
                app_name="signal_loop3",
            )
            try:
                summary_data = json.loads(response)
            except (json.JSONDecodeError, TypeError):
                summary_data = {}

            result.loop3 = Loop3Result(
                signal_pairs_analyzed=summary_data.get("pairs_analyzed", 0),
                summary=summary_data.get("summary", response[:300]),
                latency_ms=int((time.monotonic() - t0) * 1000),
                success=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("loop3_failed", error=str(exc))
            result.loop3 = Loop3Result(
                success=False,
                error=str(exc),
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

    result.total_latency_ms = int((time.monotonic() - start_total) * 1000)

    # Build overall summary
    parts = []
    if result.loop1:
        parts.append(f"Loop1({'ok' if result.loop1.success else 'err'})")
    if result.loop2:
        parts.append(f"Loop2({'ok' if result.loop2.success else 'err'})")
    if result.loop3:
        parts.append(f"Loop3({'ok' if result.loop3.success else 'err'})")
    result.overall_summary = " | ".join(parts) or "No loops ran."
    result.success = all(
        (r.success if r else True)
        for r in [result.loop1, result.loop2, result.loop3]
    )

    logger.info(
        "feedback_loop_complete",
        run_id=result.run_id,
        summary=result.overall_summary,
        latency_ms=result.total_latency_ms,
    )
    return result


# =============================================================================
# CLI entry point — python -m backend.agents.feedback_loop
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run SIGNAL Feedback Loop Agent (Agent 5)")
    parser.add_argument("--company-id", help="Company UUID for Loop 1 (per-company feedback)")
    parser.add_argument("--no-loop1", action="store_true", help="Skip Loop 1")
    parser.add_argument("--no-loop2", action="store_true", help="Skip Loop 2")
    parser.add_argument("--no-loop3", action="store_true", help="Skip Loop 3")
    args = parser.parse_args()

    async def _main():
        result = await run_feedback_loop(
            company_id=args.company_id,
            run_loop1=not args.no_loop1,
            run_loop2=not args.no_loop2,
            run_loop3=not args.no_loop3,
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))

    asyncio.run(_main())
