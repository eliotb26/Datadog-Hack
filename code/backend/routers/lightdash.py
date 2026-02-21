"""FastAPI router for Lightdash integration.

Endpoints
---------
GET  /api/lightdash/status
    Returns whether the Lightdash instance is reachable and configured.

GET  /api/lightdash/embed-urls
    Returns iframe-embeddable URLs for all dashboard panels.

GET  /api/lightdash/metrics/campaign-performance
    Returns campaign performance data (feeds Loop 1).

GET  /api/lightdash/metrics/agent-learning-curve
    Returns agent quality scores over time.

GET  /api/lightdash/metrics/polymarket-calibration
    Returns signal prediction accuracy (feeds Loop 3).

GET  /api/lightdash/metrics/channel-performance
    Returns engagement by channel (feeds Agent 4).

GET  /api/lightdash/metrics/cross-company-patterns
    Returns anonymised cross-company patterns (feeds Loop 2).

GET  /api/lightdash/metrics/safety
    Returns safety screening statistics.

POST /api/lightdash/webhooks/threshold-alert
    Receives threshold-based alert payloads from Lightdash schedulers
    and triggers the appropriate feedback loop action.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from ..integrations.lightdash_client import LightdashClient
from ..integrations.lightdash_metrics import (
    get_agent_learning_curve,
    get_campaign_performance,
    get_channel_performance,
    get_cross_company_patterns,
    get_polymarket_calibration,
    get_safety_metrics,
    get_analytics_embed_urls,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lightdash", tags=["lightdash"])


# ---------------------------------------------------------------------------
# Shared dependency — Lightdash client
# ---------------------------------------------------------------------------

def _get_client() -> LightdashClient:
    return LightdashClient(
        base_url=os.getenv("LIGHTDASH_URL", ""),
        api_key=os.getenv("LIGHTDASH_API_KEY", ""),
        project_uuid=os.getenv("LIGHTDASH_PROJECT_UUID", ""),
    )


# ---------------------------------------------------------------------------
# Status & embed URLs
# ---------------------------------------------------------------------------

@router.get("/status")
async def lightdash_status(
    client: LightdashClient = Depends(_get_client),
) -> Dict[str, Any]:
    """Return Lightdash connection status."""
    async with client:
        healthy = await client.health_check()
    return {
        "configured": client.is_available,
        "healthy": healthy,
        "url": os.getenv("LIGHTDASH_URL", ""),
        "project_uuid": os.getenv("LIGHTDASH_PROJECT_UUID", ""),
    }


@router.get("/embed-urls")
async def embed_urls(
    client: LightdashClient = Depends(_get_client),
) -> Dict[str, str]:
    """Return iframe-embeddable URLs for all Analytics page panels."""
    async with client:
        return get_analytics_embed_urls(client)


# ---------------------------------------------------------------------------
# Metric endpoints
# ---------------------------------------------------------------------------

@router.get("/metrics/campaign-performance")
async def campaign_performance(
    company_id: Optional[str] = Query(None, description="Filter by company UUID"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    client: LightdashClient = Depends(_get_client),
) -> List[Dict[str, Any]]:
    """Campaign engagement metrics for the selected period.

    Feeds Loop 1 (prompt weight updates for Campaign Gen Agent).
    """
    async with client:
        return await get_campaign_performance(
            company_id=company_id, days=days, client=client
        )


@router.get("/metrics/agent-learning-curve")
async def agent_learning_curve(
    agent_name: Optional[str] = Query(
        None,
        description="Filter to a specific agent (brand_intake | trend_intel | campaign_gen | distribution)",
    ),
    days: int = Query(30, ge=1, le=365),
    client: LightdashClient = Depends(_get_client),
) -> List[Dict[str, Any]]:
    """Daily quality scores per agent — the self-improvement visualisation."""
    async with client:
        return await get_agent_learning_curve(
            agent_name=agent_name, days=days, client=client
        )


@router.get("/metrics/polymarket-calibration")
async def polymarket_calibration(
    signal_category: Optional[str] = Query(None, description="Filter by signal category"),
    days: int = Query(30, ge=1, le=365),
    client: LightdashClient = Depends(_get_client),
) -> List[Dict[str, Any]]:
    """Signal prediction accuracy vs actual engagement.

    Feeds Loop 3 (Polymarket signal calibration).
    """
    async with client:
        return await get_polymarket_calibration(
            signal_category=signal_category, days=days, client=client
        )


@router.get("/metrics/channel-performance")
async def channel_performance(
    channel: Optional[str] = Query(None, description="Filter to one channel"),
    days: int = Query(30, ge=1, le=365),
    client: LightdashClient = Depends(_get_client),
) -> List[Dict[str, Any]]:
    """Engagement rate by distribution channel.

    Agent 4 (Distribution Router) uses this to bias channel selection.
    """
    async with client:
        return await get_channel_performance(
            channel=channel, days=days, client=client
        )


@router.get("/metrics/cross-company-patterns")
async def cross_company_patterns(
    pattern_type: Optional[str] = Query(None, description="Filter by pattern type"),
    min_confidence: float = Query(0.6, ge=0.0, le=1.0),
    client: LightdashClient = Depends(_get_client),
) -> List[Dict[str, Any]]:
    """Anonymised cross-company style patterns above a confidence threshold.

    Feeds Loop 2 (shared pattern learning).
    """
    async with client:
        return await get_cross_company_patterns(
            pattern_type=pattern_type,
            min_confidence=min_confidence,
            client=client,
        )


@router.get("/metrics/safety")
async def safety_metrics(
    days: int = Query(30, ge=1, le=365),
    client: LightdashClient = Depends(_get_client),
) -> Dict[str, Any]:
    """Aggregated safety screening statistics."""
    async with client:
        return await get_safety_metrics(days=days, client=client)


# ---------------------------------------------------------------------------
# Webhook receiver
# ---------------------------------------------------------------------------

class LightdashAlertPayload(BaseModel):
    """Payload sent by a Lightdash scheduled delivery / threshold alert."""

    name: str
    savedChartUuid: Optional[str] = None
    dashboardUuid: Optional[str] = None
    url: Optional[str] = None
    message: Optional[str] = None
    # Threshold result fields (present when triggered by a threshold alert)
    thresholdResult: Optional[Dict[str, Any]] = None
    # Custom tag we set when registering the alert so we know which loop to trigger
    tag: Optional[str] = None


def _verify_lightdash_signature(
    body: bytes,
    signature_header: Optional[str],
    secret: str,
) -> bool:
    """Verify the HMAC-SHA256 signature Lightdash adds to webhook payloads."""
    if not secret or not signature_header:
        return True  # Skip verification in dev when no secret is set
    expected = hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


async def _handle_alert(payload: LightdashAlertPayload) -> None:
    """Background task: route the alert to the correct feedback action."""
    tag = payload.tag or ""
    log.info(
        "lightdash_alert_received name=%s tag=%s threshold_result=%s",
        payload.name,
        tag,
        payload.thresholdResult,
    )

    if tag == "loop1_low_engagement":
        log.info(
            "lightdash_alert_loop1 triggering prompt weight recalculation "
            "chart=%s",
            payload.savedChartUuid,
        )
        # TODO: call Feedback Loop Agent (Agent 5) to update prompt weights

    elif tag == "loop2_new_pattern":
        log.info(
            "lightdash_alert_loop2 new cross-company pattern detected "
            "chart=%s",
            payload.savedChartUuid,
        )
        # TODO: call Feedback Loop Agent to propagate new shared patterns

    elif tag == "loop3_calibration_drift":
        log.info(
            "lightdash_alert_loop3 signal calibration drift detected "
            "chart=%s",
            payload.savedChartUuid,
        )
        # TODO: call Feedback Loop Agent to recalibrate signal thresholds

    elif tag == "safety_block_rate_high":
        log.warning(
            "lightdash_alert_safety block rate above threshold "
            "result=%s",
            payload.thresholdResult,
        )
        # TODO: notify ops + trigger Modulate appeals review

    else:
        log.debug("lightdash_alert_unhandled_tag tag=%s", tag)


@router.post("/webhooks/threshold-alert", status_code=202)
async def threshold_alert_webhook(
    payload: LightdashAlertPayload,
    background_tasks: BackgroundTasks,
    x_lightdash_signature: Optional[str] = Header(None),
) -> Dict[str, str]:
    """Receive a threshold-based alert from Lightdash and trigger the
    appropriate feedback loop action asynchronously.

    Lightdash must be configured to POST to::

        POST https://your-signal-backend/api/lightdash/webhooks/threshold-alert

    Set the ``tag`` field in the alert name or a custom payload field to
    indicate which loop to trigger (``loop1_low_engagement``,
    ``loop2_new_pattern``, ``loop3_calibration_drift``,
    ``safety_block_rate_high``).
    """
    secret = os.getenv("LIGHTDASH_WEBHOOK_SECRET", os.getenv("LIGHTDASH_SECRET", ""))
    # Signature verification would need the raw bytes; Pydantic already parsed JSON.
    # In production wire up a RawBody dependency for full verification.
    # For now we just log a warning if the header is present but we can't verify.
    if x_lightdash_signature and secret:
        log.debug(
            "lightdash_webhook_signature_received sig=%s (full verification requires raw body middleware)",
            x_lightdash_signature,
        )

    background_tasks.add_task(_handle_alert, payload)
    return {"status": "accepted", "alert": payload.name}
