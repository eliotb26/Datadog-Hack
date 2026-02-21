"""High-level Lightdash metrics interface for SIGNAL feedback loops.

Each function is responsible for one "analytical question" that powers
a self-improvement loop or agent decision.  Functions first try to query
Lightdash; if the instance is unavailable they fall back to querying the
local SQLite database directly so the platform always has data to work with.

Dashboard panel mapping
-----------------------
get_campaign_performance()      → Campaign Performance panel  (feeds Loop 1)
get_agent_learning_curve()      → Agent Learning Curve panel  (shows improvement)
get_polymarket_calibration()    → Polymarket Calibration panel (feeds Loop 3)
get_channel_performance()       → Channel Performance panel   (feeds Agent 4)
get_cross_company_patterns()    → Cross-Company Patterns panel (feeds Loop 2)
get_safety_metrics()            → Safety Metrics panel        (feeds Modulate)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from .lightdash_client import LightdashClient

log = logging.getLogger(__name__)

# Default SQLite path — mirrors database.py
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "signal.db"


# ---------------------------------------------------------------------------
# Helper: direct SQLite fallback
# ---------------------------------------------------------------------------

async def _query_sqlite(
    sql: str,
    params: tuple = (),
    db_path: Path = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Run a read-only SELECT against the local SQLite database."""
    if not db_path.exists():
        log.debug("lightdash_metrics sqlite_fallback db_not_found path=%s", db_path)
        return []
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as exc:
        log.warning("lightdash_metrics sqlite_fallback_failed error=%s", exc)
        return []


def _days_ago(days: int) -> str:
    """Return ISO timestamp string for N days ago."""
    return (datetime.utcnow() - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Campaign Performance  (Loop 1 — prompt weight updates)
# ---------------------------------------------------------------------------

async def get_campaign_performance(
    company_id: Optional[str] = None,
    days: int = 30,
    client: Optional[LightdashClient] = None,
    db_path: Path = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Return per-campaign engagement metrics for the past *days* days.

    Each row contains:
    - ``campaign_id``
    - ``headline``
    - ``channel``
    - ``confidence_score``
    - ``impressions``, ``clicks``, ``engagement_rate``
    - ``sentiment_score``
    - ``created_at``

    Used by the Feedback Loop Agent to adjust Campaign Gen Agent prompt weights.
    """
    if client and client.is_available:
        filters: Dict[str, Any] = {
            "dimensions": {
                "and": [
                    {
                        "id": "date_filter",
                        "target": {"fieldId": "campaigns_created_at"},
                        "operator": "inThePast",
                        "values": [str(days), "days"],
                    }
                ]
            }
        }
        if company_id:
            filters["dimensions"]["and"].append(
                {
                    "id": "company_filter",
                    "target": {"fieldId": "campaigns_company_id"},
                    "operator": "equals",
                    "values": [company_id],
                }
            )
        result = await client.run_metric_query(
            explore_name="campaigns",
            dimensions=[
                "campaigns_id",
                "campaigns_headline",
                "campaigns_channel_recommendation",
                "campaigns_created_at_date",
            ],
            metrics=[
                "campaign_metrics_avg_impressions",
                "campaign_metrics_avg_clicks",
                "campaign_metrics_avg_engagement_rate",
                "campaign_metrics_avg_sentiment_score",
                "campaigns_avg_confidence_score",
            ],
            filters=filters,
            sort_by=[{"fieldId": "campaigns_created_at_date", "descending": True}],
            limit=200,
        )
        rows = result.get("rows", [])
        if rows:
            return rows

    # --- SQLite fallback ---
    company_clause = "AND c.company_id = ?" if company_id else ""
    params: tuple = (company_id, _days_ago(days)) if company_id else (_days_ago(days),)
    sql = f"""
        SELECT
            c.id            AS campaign_id,
            c.headline,
            c.channel_recommendation AS channel,
            c.confidence_score,
            COALESCE(m.impressions, 0)      AS impressions,
            COALESCE(m.clicks, 0)           AS clicks,
            COALESCE(m.engagement_rate, 0.0) AS engagement_rate,
            m.sentiment_score,
            c.created_at
        FROM campaigns c
        LEFT JOIN campaign_metrics m ON m.campaign_id = c.id
        WHERE c.created_at >= ?
        {company_clause}
        ORDER BY c.created_at DESC
        LIMIT 200
    """
    if company_id:
        params = (_days_ago(days), company_id)
    else:
        params = (_days_ago(days),)
    return await _query_sqlite(sql, params, db_path)


# ---------------------------------------------------------------------------
# Agent Learning Curve  (visualisation — shows system getting smarter)
# ---------------------------------------------------------------------------

async def get_agent_learning_curve(
    agent_name: Optional[str] = None,
    days: int = 30,
    client: Optional[LightdashClient] = None,
    db_path: Path = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Return daily average quality scores per agent for the past *days* days.

    Each row contains:
    - ``agent_name``
    - ``day`` (ISO date string)
    - ``avg_quality_score``
    - ``avg_latency_ms``
    - ``run_count``

    Rising ``avg_quality_score`` is the "demo power moment" showing the
    system learning over time.
    """
    if client and client.is_available:
        filters: Dict[str, Any] = {
            "dimensions": {
                "and": [
                    {
                        "id": "date_filter",
                        "target": {"fieldId": "agent_traces_created_at"},
                        "operator": "inThePast",
                        "values": [str(days), "days"],
                    }
                ]
            }
        }
        if agent_name:
            filters["dimensions"]["and"].append(
                {
                    "id": "agent_filter",
                    "target": {"fieldId": "agent_traces_agent_name"},
                    "operator": "equals",
                    "values": [agent_name],
                }
            )
        result = await client.run_metric_query(
            explore_name="agent_traces",
            dimensions=["agent_traces_agent_name", "agent_traces_created_at_date"],
            metrics=[
                "agent_traces_avg_quality_score",
                "agent_traces_avg_latency_ms",
                "agent_traces_count",
            ],
            filters=filters,
            sort_by=[{"fieldId": "agent_traces_created_at_date", "descending": False}],
            limit=500,
        )
        rows = result.get("rows", [])
        if rows:
            return rows

    # --- SQLite fallback ---
    agent_clause = "AND agent_name = ?" if agent_name else ""
    sql = f"""
        SELECT
            agent_name,
            DATE(created_at) AS day,
            AVG(quality_score)  AS avg_quality_score,
            AVG(latency_ms)     AS avg_latency_ms,
            COUNT(*)            AS run_count
        FROM agent_traces
        WHERE created_at >= ?
        {agent_clause}
        GROUP BY agent_name, DATE(created_at)
        ORDER BY agent_name, day ASC
    """
    params = (_days_ago(days), agent_name) if agent_name else (_days_ago(days),)
    return await _query_sqlite(sql, params, db_path)


# ---------------------------------------------------------------------------
# Polymarket Calibration  (Loop 3 — signal accuracy tuning)
# ---------------------------------------------------------------------------

async def get_polymarket_calibration(
    signal_category: Optional[str] = None,
    days: int = 30,
    client: Optional[LightdashClient] = None,
    db_path: Path = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Return signal prediction vs actual engagement accuracy by category.

    Each row contains:
    - ``signal_category``
    - ``probability_threshold``
    - ``predicted_engagement``
    - ``actual_engagement``
    - ``accuracy_score``
    - ``sample_size``
    - ``calibrated_at``

    Used by the Feedback Loop Agent to adjust signal scoring thresholds.
    """
    if client and client.is_available:
        filters: Dict[str, Any] = {
            "dimensions": {
                "and": [
                    {
                        "id": "date_filter",
                        "target": {"fieldId": "signal_calibration_calibrated_at"},
                        "operator": "inThePast",
                        "values": [str(days), "days"],
                    }
                ]
            }
        }
        if signal_category:
            filters["dimensions"]["and"].append(
                {
                    "id": "category_filter",
                    "target": {"fieldId": "signal_calibration_signal_category"},
                    "operator": "equals",
                    "values": [signal_category],
                }
            )
        result = await client.run_metric_query(
            explore_name="signal_calibration",
            dimensions=[
                "signal_calibration_signal_category",
                "signal_calibration_calibrated_at_date",
            ],
            metrics=[
                "signal_calibration_avg_accuracy_score",
                "signal_calibration_avg_predicted_engagement",
                "signal_calibration_avg_actual_engagement",
                "signal_calibration_count",
            ],
            filters=filters,
            sort_by=[{"fieldId": "signal_calibration_calibrated_at_date", "descending": True}],
            limit=200,
        )
        rows = result.get("rows", [])
        if rows:
            return rows

    # --- SQLite fallback ---
    category_clause = "AND signal_category = ?" if signal_category else ""
    sql = f"""
        SELECT
            signal_category,
            AVG(probability_threshold)   AS probability_threshold,
            AVG(predicted_engagement)    AS predicted_engagement,
            AVG(actual_engagement)       AS actual_engagement,
            AVG(accuracy_score)          AS accuracy_score,
            COUNT(*)                     AS sample_size,
            MAX(calibrated_at)           AS calibrated_at
        FROM signal_calibration
        WHERE calibrated_at >= ?
        {category_clause}
        GROUP BY signal_category
        ORDER BY accuracy_score DESC
    """
    params = (_days_ago(days), signal_category) if signal_category else (_days_ago(days),)
    return await _query_sqlite(sql, params, db_path)


# ---------------------------------------------------------------------------
# Channel Performance  (feeds Agent 4 routing decisions)
# ---------------------------------------------------------------------------

async def get_channel_performance(
    channel: Optional[str] = None,
    days: int = 30,
    client: Optional[LightdashClient] = None,
    db_path: Path = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Return engagement metrics grouped by distribution channel.

    Each row contains:
    - ``channel``
    - ``avg_engagement_rate``
    - ``avg_impressions``
    - ``avg_clicks``
    - ``campaign_count``

    Agent 4 (Distribution Router) uses this to bias channel selection toward
    historically better-performing channels.
    """
    if client and client.is_available:
        filters: Dict[str, Any] = {
            "dimensions": {
                "and": [
                    {
                        "id": "date_filter",
                        "target": {"fieldId": "campaign_metrics_measured_at"},
                        "operator": "inThePast",
                        "values": [str(days), "days"],
                    }
                ]
            }
        }
        if channel:
            filters["dimensions"]["and"].append(
                {
                    "id": "channel_filter",
                    "target": {"fieldId": "campaign_metrics_channel"},
                    "operator": "equals",
                    "values": [channel],
                }
            )
        result = await client.run_metric_query(
            explore_name="campaign_metrics",
            dimensions=["campaign_metrics_channel"],
            metrics=[
                "campaign_metrics_avg_engagement_rate",
                "campaign_metrics_avg_impressions",
                "campaign_metrics_avg_clicks",
                "campaign_metrics_count",
            ],
            filters=filters,
            sort_by=[{"fieldId": "campaign_metrics_avg_engagement_rate", "descending": True}],
            limit=50,
        )
        rows = result.get("rows", [])
        if rows:
            return rows

    # --- SQLite fallback ---
    channel_clause = "AND m.channel = ?" if channel else ""
    sql = f"""
        SELECT
            m.channel,
            AVG(m.engagement_rate) AS avg_engagement_rate,
            AVG(m.impressions)     AS avg_impressions,
            AVG(m.clicks)          AS avg_clicks,
            COUNT(DISTINCT m.campaign_id) AS campaign_count
        FROM campaign_metrics m
        WHERE m.measured_at >= ?
        {channel_clause}
        GROUP BY m.channel
        ORDER BY avg_engagement_rate DESC
    """
    params = (_days_ago(days), channel) if channel else (_days_ago(days),)
    return await _query_sqlite(sql, params, db_path)


# ---------------------------------------------------------------------------
# Cross-Company Patterns  (Loop 2 — shared style learning)
# ---------------------------------------------------------------------------

async def get_cross_company_patterns(
    pattern_type: Optional[str] = None,
    min_confidence: float = 0.6,
    client: Optional[LightdashClient] = None,
    db_path: Path = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Return anonymised cross-company patterns above the confidence threshold.

    Each row contains:
    - ``pattern_type``
    - ``description``
    - ``conditions``
    - ``effect``
    - ``confidence``
    - ``sample_size``

    The Feedback Loop Agent uses these to inject globally learned best
    practices into per-company prompt weights.
    """
    if client and client.is_available:
        filters: Dict[str, Any] = {
            "dimensions": {
                "and": [
                    {
                        "id": "confidence_filter",
                        "target": {"fieldId": "shared_patterns_confidence"},
                        "operator": "greaterThanOrEqual",
                        "values": [str(min_confidence)],
                    }
                ]
            }
        }
        if pattern_type:
            filters["dimensions"]["and"].append(
                {
                    "id": "type_filter",
                    "target": {"fieldId": "shared_patterns_pattern_type"},
                    "operator": "equals",
                    "values": [pattern_type],
                }
            )
        result = await client.run_metric_query(
            explore_name="shared_patterns",
            dimensions=[
                "shared_patterns_pattern_type",
                "shared_patterns_description",
                "shared_patterns_conditions",
                "shared_patterns_effect",
            ],
            metrics=[
                "shared_patterns_avg_confidence",
                "shared_patterns_total_sample_size",
            ],
            filters=filters,
            sort_by=[{"fieldId": "shared_patterns_avg_confidence", "descending": True}],
            limit=100,
        )
        rows = result.get("rows", [])
        if rows:
            return rows

    # --- SQLite fallback ---
    type_clause = "AND pattern_type = ?" if pattern_type else ""
    sql = f"""
        SELECT
            pattern_type,
            description,
            conditions,
            effect,
            confidence,
            sample_size,
            discovered_at
        FROM shared_patterns
        WHERE confidence >= ?
        {type_clause}
        ORDER BY confidence DESC, sample_size DESC
        LIMIT 100
    """
    params = (min_confidence, pattern_type) if pattern_type else (min_confidence,)
    return await _query_sqlite(sql, params, db_path)


# ---------------------------------------------------------------------------
# Safety Metrics  (feeds Modulate AI improvement)
# ---------------------------------------------------------------------------

async def get_safety_metrics(
    days: int = 30,
    client: Optional[LightdashClient] = None,
    db_path: Path = _DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """Return aggregated safety screening statistics.

    Returns a dict with:
    - ``total_campaigns``
    - ``blocked_count``
    - ``block_rate``
    - ``avg_safety_score``
    - ``passed_count``

    These feed back to improve Modulate AI moderation accuracy over time.
    """
    empty: Dict[str, Any] = {
        "total_campaigns": 0,
        "blocked_count": 0,
        "block_rate": 0.0,
        "avg_safety_score": None,
        "passed_count": 0,
    }
    if client and client.is_available:
        result = await client.run_metric_query(
            explore_name="campaigns",
            dimensions=[],
            metrics=[
                "campaigns_count",
                "campaigns_blocked_count",
                "campaigns_avg_safety_score",
                "campaigns_passed_count",
            ],
            filters={
                "dimensions": {
                    "and": [
                        {
                            "id": "date_filter",
                            "target": {"fieldId": "campaigns_created_at"},
                            "operator": "inThePast",
                            "values": [str(days), "days"],
                        }
                    ]
                }
            },
            limit=1,
        )
        rows = result.get("rows", [])
        if rows:
            return rows[0]

    # --- SQLite fallback ---
    sql = """
        SELECT
            COUNT(*)                          AS total_campaigns,
            SUM(CASE WHEN safety_passed = 0 THEN 1 ELSE 0 END) AS blocked_count,
            AVG(safety_score)                 AS avg_safety_score,
            SUM(CASE WHEN safety_passed = 1 THEN 1 ELSE 0 END) AS passed_count
        FROM campaigns
        WHERE created_at >= ?
    """
    rows = await _query_sqlite(sql, (_days_ago(days),), db_path)
    if not rows:
        return empty
    row = rows[0]
    total = row.get("total_campaigns") or 0
    blocked = row.get("blocked_count") or 0
    return {
        "total_campaigns": total,
        "blocked_count": blocked,
        "block_rate": round(blocked / total, 4) if total else 0.0,
        "avg_safety_score": row.get("avg_safety_score"),
        "passed_count": row.get("passed_count") or 0,
    }


# ---------------------------------------------------------------------------
# Dashboard embed URLs (for frontend Analytics page)
# ---------------------------------------------------------------------------

def get_analytics_embed_urls(
    client: Optional[LightdashClient] = None,
) -> Dict[str, str]:
    """Return embed URLs for each dashboard panel.

    Returns an empty string for any panel whose UUID is not configured.
    Frontend uses these to render ``<iframe>`` elements on the Analytics page.
    """
    import os

    lc = client or LightdashClient()
    return {
        "campaign_performance": lc.get_dashboard_embed_url(
            os.getenv("LIGHTDASH_DASHBOARD_CAMPAIGN_PERF_UUID", "")
        ),
        "agent_learning_curve": lc.get_dashboard_embed_url(
            os.getenv("LIGHTDASH_DASHBOARD_LEARNING_CURVE_UUID", "")
        ),
        "polymarket_calibration": lc.get_dashboard_embed_url(
            os.getenv("LIGHTDASH_DASHBOARD_CALIBRATION_UUID", "")
        ),
        "channel_performance": lc.get_dashboard_embed_url(
            os.getenv("LIGHTDASH_DASHBOARD_CHANNEL_PERF_UUID", "")
        ),
        "cross_company_patterns": lc.get_dashboard_embed_url(
            os.getenv("LIGHTDASH_DASHBOARD_PATTERNS_UUID", "")
        ),
        "safety_metrics": lc.get_dashboard_embed_url(
            os.getenv("LIGHTDASH_DASHBOARD_SAFETY_UUID", "")
        ),
    }
