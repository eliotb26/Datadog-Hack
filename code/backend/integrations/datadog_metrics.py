"""Datadog custom metrics helper for SIGNAL agents.

Sends StatsD metrics to the Datadog Agent.
Falls back silently when DD_API_KEY is not configured (local dev).

Metric catalogue
----------------
Polymarket:
  signal.polymarket.signals_active       gauge    active signals surfaced
  signal.polymarket.markets_fetched      gauge    markets pulled from Gamma API
  signal.polymarket.signals_after_filter gauge    markets remaining after filter
  signal.polymarket.poll_latency_ms      histogram full poll cycle duration
  signal.polymarket.api_errors           increment Polymarket API failure count

Agents (generic):
  signal.agent.runs                      increment total agent invocations
  signal.agent.latency_ms               histogram full agent run duration
  signal.agent.run_latency_ms           histogram per-run latency (tagged by agent/status)
  signal.agent.signals_returned         gauge     signals returned per Trend Agent run
  signal.agent.concepts_generated       gauge     concepts produced per Campaign Agent run
  signal.agent.tokens_used              histogram LLM tokens consumed per run
  signal.agent.errors                   increment agent error count (tagged by agent/error_type)

Campaigns:
  signal.campaigns.generated            increment concepts generated in one cycle
  signal.campaigns.approved             increment concepts that passed all checks
  signal.campaigns.blocked_safety       increment concepts blocked by safety layer

API calls:
  signal.api.calls                       increment external API call count
  signal.api.latency_ms                 histogram external API call latency

Feedback loop:
  signal.feedback.loop_duration_ms      histogram full feedback loop duration
  signal.feedback.prompt_quality_score  gauge     quality score for a prompt weight set
  signal.feedback.weight_updates        increment prompt-weight update events

Modulate safety (text + voice):
  signal.modulate.safety_checks         increment every safety screen run
  signal.modulate.safety_blocked        increment campaigns blocked by safety layer
  signal.modulate.safety_passed         increment campaigns that passed safety check
  signal.modulate.safety_score          histogram toxicity score distribution (0–1)
  signal.modulate.safety_latency_ms     histogram time taken for one safety screen
  signal.modulate.appeals               increment human-override (appeal) events
  signal.modulate.voice_briefs          increment voice briefs processed via Velma-2
  signal.modulate.voice_latency_ms      histogram Velma-2 transcription latency
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Generator, List, Optional

import structlog

log = structlog.get_logger(__name__)

_dd_initialized = False


def _ensure_initialized() -> None:
    global _dd_initialized
    if _dd_initialized:
        return
    api_key = os.getenv("DD_API_KEY", "")
    if not api_key or api_key == "your_datadog_api_key_here":
        log.debug("datadog_metrics_disabled", reason="DD_API_KEY not set")
        return
    try:
        from datadog import initialize

        initialize(
            statsd_host=os.getenv("DD_AGENT_HOST", "localhost"),
            statsd_port=int(os.getenv("DD_STATSD_PORT", "8125")),
        )
        _dd_initialized = True
        log.info("datadog_metrics_initialized")
    except Exception as exc:  # noqa: BLE001
        log.warning("datadog_init_failed", error=str(exc))


def _statsd():
    """Return the statsd client if available, else None."""
    _ensure_initialized()
    if not _dd_initialized:
        return None
    try:
        from datadog import statsd

        return statsd
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Polymarket metrics
# ---------------------------------------------------------------------------


def track_signals_surfaced(count: int, company_id: str = "unknown") -> None:
    """Gauge: number of trend signals surfaced in this cycle."""
    sd = _statsd()
    if sd:
        sd.gauge("signal.polymarket.signals_active", count, tags=[f"company:{company_id}"])
    log.info("metric.signals_surfaced", count=count, company_id=company_id)


def track_polymarket_poll(
    markets_fetched: int,
    signals_after_filter: int,
    latency_ms: float,
) -> None:
    """Record one full Polymarket polling cycle."""
    sd = _statsd()
    if sd:
        sd.gauge("signal.polymarket.markets_fetched", markets_fetched)
        sd.gauge("signal.polymarket.signals_after_filter", signals_after_filter)
        sd.histogram("signal.polymarket.poll_latency_ms", latency_ms)
    log.info(
        "metric.polymarket_poll",
        markets_fetched=markets_fetched,
        signals_after_filter=signals_after_filter,
        latency_ms=round(latency_ms, 1),
    )


def track_polymarket_error() -> None:
    """Increment Polymarket API error counter."""
    sd = _statsd()
    if sd:
        sd.increment("signal.polymarket.api_errors")
    log.warning("metric.polymarket_api_error")


# ---------------------------------------------------------------------------
# Generic agent metrics
# ---------------------------------------------------------------------------


def track_agent_latency(duration_ms: float, agent_name: str = "trend_intel") -> None:
    """Histogram: time taken for one full agent run."""
    sd = _statsd()
    if sd:
        sd.histogram("signal.agent.latency_ms", duration_ms, tags=[f"agent:{agent_name}"])
    log.info("metric.agent_latency", agent=agent_name, latency_ms=round(duration_ms, 1))


def track_agent_tokens(tokens: int, agent_name: str) -> None:
    """Histogram: LLM tokens consumed in one agent run."""
    sd = _statsd()
    if sd:
        sd.histogram("signal.agent.tokens_used", tokens, tags=[f"agent:{agent_name}"])
    log.info("metric.agent_tokens", agent=agent_name, tokens=tokens)


def track_agent_error(agent_name: str, error_type: str = "unknown") -> None:
    """Increment agent error counter tagged by agent name and error type."""
    sd = _statsd()
    if sd:
        sd.increment(
            "signal.agent.errors",
            tags=[f"agent:{agent_name}", f"error:{error_type}"],
        )
    log.warning("metric.agent_error", agent=agent_name, error_type=error_type)


# ---------------------------------------------------------------------------
# API call metrics
# ---------------------------------------------------------------------------


def track_api_call(api: str, success: bool, latency_ms: Optional[float] = None) -> None:
    """Increment API call counter with success/error tag."""
    sd = _statsd()
    status = "success" if success else "error"
    if sd:
        sd.increment("signal.api.calls", tags=[f"api:{api}", f"status:{status}"])
        if latency_ms is not None:
            sd.histogram("signal.api.latency_ms", latency_ms, tags=[f"api:{api}"])
    log.debug("metric.api_call", api=api, status=status, latency_ms=latency_ms)


# ---------------------------------------------------------------------------
# Per-agent run bundles
# ---------------------------------------------------------------------------


def track_trend_agent_run(
    signals_returned: int,
    company_id: str,
    latency_ms: float,
    success: bool,
) -> None:
    """Full Agent 2 (Trend Intelligence) run metric bundle."""
    sd = _statsd()
    status = "success" if success else "error"
    tags = [f"company:{company_id}", f"status:{status}", "agent:trend_intel"]
    if sd:
        sd.increment("signal.agent.runs", tags=tags)
        sd.gauge("signal.agent.signals_returned", signals_returned, tags=tags)
        sd.histogram("signal.agent.run_latency_ms", latency_ms, tags=tags)
    log.info(
        "metric.trend_agent_run",
        company_id=company_id,
        signals=signals_returned,
        latency_ms=round(latency_ms, 1),
        status=status,
    )


def track_campaign_agent_run(
    concepts_generated: int,
    company_id: str,
    latency_ms: float,
    success: bool,
) -> None:
    """Full Agent 3 (Campaign Generation) run metric bundle."""
    sd = _statsd()
    status = "success" if success else "error"
    tags = [f"company:{company_id}", f"status:{status}", "agent:campaign_gen"]
    if sd:
        sd.increment("signal.agent.runs", tags=tags)
        sd.gauge("signal.agent.concepts_generated", concepts_generated, tags=tags)
        sd.histogram("signal.agent.run_latency_ms", latency_ms, tags=tags)
    log.info(
        "metric.campaign_agent_run",
        company_id=company_id,
        concepts=concepts_generated,
        latency_ms=round(latency_ms, 1),
        status=status,
    )


# ---------------------------------------------------------------------------
# Campaign lifecycle metrics
# ---------------------------------------------------------------------------


def track_campaign_generated(count: int = 1, company_id: str = "unknown") -> None:
    """Increment counter when campaign concepts are generated."""
    sd = _statsd()
    if sd:
        sd.increment("signal.campaigns.generated", count, tags=[f"company:{company_id}"])
    log.info("metric.campaign_generated", count=count, company_id=company_id)


def track_campaign_approved(company_id: str = "unknown") -> None:
    """Increment counter when a campaign concept passes all checks."""
    sd = _statsd()
    if sd:
        sd.increment("signal.campaigns.approved", tags=[f"company:{company_id}"])
    log.info("metric.campaign_approved", company_id=company_id)


def track_campaign_blocked_safety(company_id: str = "unknown", safety_score: Optional[float] = None) -> None:
    """Increment counter when a campaign concept is blocked by the safety layer."""
    sd = _statsd()
    if sd:
        sd.increment("signal.campaigns.blocked_safety", tags=[f"company:{company_id}"])
    log.warning(
        "metric.campaign_blocked_safety",
        company_id=company_id,
        safety_score=safety_score,
    )


# ---------------------------------------------------------------------------
# Feedback loop metrics
# ---------------------------------------------------------------------------


def track_feedback_loop(loop_duration_ms: float, loop_number: int = 1) -> None:
    """Histogram: full feedback loop (self-improvement cycle) duration."""
    sd = _statsd()
    if sd:
        sd.histogram(
            "signal.feedback.loop_duration_ms",
            loop_duration_ms,
            tags=[f"loop:{loop_number}"],
        )
    log.info(
        "metric.feedback_loop",
        loop_number=loop_number,
        loop_duration_ms=round(loop_duration_ms, 1),
    )


def track_prompt_quality(score: float, agent_name: str) -> None:
    """Gauge: prompt weight quality score after a feedback cycle."""
    sd = _statsd()
    if sd:
        sd.gauge(
            "signal.feedback.prompt_quality_score",
            score,
            tags=[f"agent:{agent_name}"],
        )
    log.info("metric.prompt_quality", agent=agent_name, score=round(score, 4))


def track_weight_update(agent_name: str, weight_key: str = "unknown") -> None:
    """Increment counter when a prompt weight is updated by the feedback loop."""
    sd = _statsd()
    if sd:
        sd.increment(
            "signal.feedback.weight_updates",
            tags=[f"agent:{agent_name}", f"weight:{weight_key}"],
        )
    log.info("metric.weight_update", agent=agent_name, weight_key=weight_key)


# ---------------------------------------------------------------------------
# Generic timed context manager
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Modulate safety + voice metrics
# ---------------------------------------------------------------------------


def track_modulate_safety_check(
    company_id: str = "unknown",
    blocked: bool = False,
    toxicity_score: Optional[float] = None,
    latency_ms: Optional[float] = None,
    method: str = "text_heuristic",
) -> None:
    """Record one Modulate safety screen result."""
    sd = _statsd()
    status = "blocked" if blocked else "passed"
    tags = [f"company:{company_id}", f"status:{status}", f"method:{method}"]
    if sd:
        sd.increment("signal.modulate.safety_checks", tags=tags)
        if blocked:
            sd.increment("signal.modulate.safety_blocked", tags=[f"company:{company_id}"])
        else:
            sd.increment("signal.modulate.safety_passed", tags=[f"company:{company_id}"])
        if toxicity_score is not None:
            sd.histogram("signal.modulate.safety_score", toxicity_score, tags=[f"company:{company_id}"])
        if latency_ms is not None:
            sd.histogram("signal.modulate.safety_latency_ms", latency_ms, tags=tags)
    log.info(
        "metric.modulate_safety",
        company_id=company_id,
        blocked=blocked,
        toxicity_score=round(toxicity_score, 4) if toxicity_score is not None else None,
        latency_ms=round(latency_ms, 1) if latency_ms is not None else None,
        method=method,
    )


def track_modulate_appeal(company_id: str = "unknown") -> None:
    """Increment counter when a human reviewer overrides a safety block."""
    sd = _statsd()
    if sd:
        sd.increment("signal.modulate.appeals", tags=[f"company:{company_id}"])
    log.info("metric.modulate_appeal", company_id=company_id)


def track_modulate_voice_brief(
    company_id: str = "unknown",
    success: bool = True,
    latency_ms: Optional[float] = None,
) -> None:
    """Record one Velma-2 voice brief transcription."""
    sd = _statsd()
    status = "success" if success else "error"
    tags = [f"company:{company_id}", f"status:{status}"]
    if sd:
        sd.increment("signal.modulate.voice_briefs", tags=tags)
        if latency_ms is not None:
            sd.histogram("signal.modulate.voice_latency_ms", latency_ms, tags=tags)
    log.info(
        "metric.modulate_voice_brief",
        company_id=company_id,
        success=success,
        latency_ms=round(latency_ms, 1) if latency_ms is not None else None,
    )


@contextmanager
def timed(metric_name: str, tags: Optional[List[str]] = None) -> Generator[None, None, None]:
    """Context manager that records execution time as a histogram metric."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        sd = _statsd()
        if sd:
            sd.histogram(metric_name, elapsed_ms, tags=tags or [])
        log.debug("timed_block", metric=metric_name, elapsed_ms=round(elapsed_ms, 1))
