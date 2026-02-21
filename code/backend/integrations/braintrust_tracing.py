"""
SIGNAL — Braintrust Tracing Integration

Traces agent runs to Braintrust for evaluation and self-improvement.
Falls back to no-op when BRAINTRUST_API_KEY is not configured.

Usage:
    from backend.integrations.braintrust_tracing import TracedRun, score_campaign_concept

    with TracedRun("campaign_gen", input={"company": ...}) as span:
        result = await run_campaign_agent(...)
        span.log_output(output=result, scores={"quality": 0.87})
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog

if TYPE_CHECKING:
    from backend.models.campaign import CampaignConcept, DistributionPlan
    from backend.models.company import CompanyProfile

log = structlog.get_logger(__name__)

_bt_logger: Any = None
_bt_initialized = False


def _ensure_initialized() -> bool:
    """Lazy-init Braintrust logger. Returns True if configured and ready."""
    global _bt_logger, _bt_initialized
    if _bt_initialized:
        return _bt_logger is not None

    _bt_initialized = True
    api_key = os.getenv("BRAINTRUST_API_KEY", "")
    if not api_key or api_key == "your_braintrust_api_key_here":
        log.debug("braintrust_disabled", reason="BRAINTRUST_API_KEY not set")
        return False

    try:
        from braintrust import init_logger

        project = os.getenv("BRAINTRUST_PROJECT", "signal")
        _bt_logger = init_logger(project=project, api_key=api_key)
        log.info("braintrust_initialized", project=project)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("braintrust_init_failed", error=str(exc))
        _bt_logger = None
        return False


def get_logger() -> Optional[Any]:
    """Return the Braintrust logger if configured, else None."""
    if not _ensure_initialized():
        return None
    return _bt_logger


# ---------------------------------------------------------------------------
# Scorer functions (0.0–1.0) for Braintrust scores
# ---------------------------------------------------------------------------


def score_campaign_concept(concept: "CampaignConcept") -> float:
    """
    Deterministic quality score for a campaign concept.
    Based on headline length, body word count, and confidence.
    """
    score = 0.0
    # Headline: 5–15 words ideal
    headline_words = len((concept.headline or "").split())
    if 5 <= headline_words <= 15:
        score += 0.4
    elif 3 <= headline_words <= 20:
        score += 0.25
    else:
        score += 0.1

    # Body: 50–150 words ideal
    body_words = len((concept.body_copy or "").split())
    if 50 <= body_words <= 150:
        score += 0.4
    elif 20 <= body_words <= 200:
        score += 0.25
    else:
        score += 0.1

    # Confidence
    score += 0.2 * (concept.confidence_score or 0.5)

    return min(1.0, round(score, 3))


def score_brand_alignment(concept: "CampaignConcept", company: "CompanyProfile") -> float:
    """
    Heuristic brand alignment score.
    Checks overlap between concept text and company goals/audience/tone.
    """
    text = f"{(concept.headline or '')} {(concept.body_copy or '')}".lower()
    keywords: List[str] = []

    if company.campaign_goals:
        keywords.extend(company.campaign_goals.lower().split()[:5])
    if company.target_audience:
        keywords.extend(company.target_audience.lower().split()[:5])
    if company.tone_of_voice:
        keywords.extend(company.tone_of_voice.lower().split()[:3])

    if not keywords:
        return 0.5  # Neutral when no profile data

    matches = sum(1 for kw in keywords if len(kw) > 3 and kw in text)
    return min(1.0, round(0.3 + 0.7 * (matches / max(1, len(keywords))), 3))


def score_distribution_plan(plan: "DistributionPlan") -> float:
    """
    Quality score for a distribution plan.
    Based on channel coverage and confidence.
    """
    if not plan.channel_scores:
        return plan.confidence if hasattr(plan, "confidence") else 0.5

    scores = [s.fit_score for s in plan.channel_scores]
    avg = sum(scores) / len(scores) if scores else 0.5
    best = max(scores) if scores else 0.5
    confidence = getattr(plan, "confidence", 0.5)

    # Reward: good spread + high best score + confidence
    spread = max(scores) - min(scores) if len(scores) > 1 else 0.2
    return min(1.0, round(0.4 * best + 0.3 * confidence + 0.2 * avg + 0.1 * min(1.0, spread * 2), 3))


# ---------------------------------------------------------------------------
# TracedRun context manager
# ---------------------------------------------------------------------------


@contextmanager
def TracedRun(
    name: str,
    *,
    input: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
):
    """
    Context manager that creates a Braintrust span for an agent run.

    Usage:
        with TracedRun("campaign_gen", input={"company_id": "..."}) as span:
            result = await run_campaign_agent(...)
            span.log_output(output=result, scores={"quality": 0.87})
    """
    logger = get_logger()

    class SpanHelper:
        def __init__(self, span: Optional[Any] = None) -> None:
            self._span = span

        def log_output(
            self,
            output: Any = None,
            scores: Optional[Dict[str, float]] = None,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> None:
            if self._span:
                try:
                    kwargs: Dict[str, Any] = {}
                    if output is not None:
                        kwargs["output"] = _serialize_for_log(output)
                    if scores:
                        kwargs["scores"] = scores
                    if metadata:
                        kwargs["metadata"] = metadata
                    if kwargs:
                        self._span.log(**kwargs)
                except Exception as exc:  # noqa: BLE001
                    log.warning("braintrust_span_log_failed", name=name, error=str(exc))

    if not logger:
        yield SpanHelper(span=None)
        return

    try:
        base_meta = {
            "agent": name,
            "environment": os.getenv("ENVIRONMENT", "development"),
        }
        base_meta.update(metadata or {})

        with logger.start_span(
            name=name,
            span_attributes={"type": "task"},
            input=_serialize_for_log(input) if input else None,
            metadata=base_meta,
            tags=tags or [name, "signal"],
        ) as span:
            try:
                yield SpanHelper(span=span)
            except asyncio.CancelledError:
                # Preserve cancellation semantics; annotate span when possible.
                try:
                    span.log(metadata={"cancelled": True})
                except Exception:  # noqa: BLE001
                    pass
                log.info("braintrust_span_cancelled", name=name)
                raise
    except Exception as exc:  # noqa: BLE001
        # Log the tracing error but ALWAYS re-raise so the caller sees the real error.
        # A second yield here is illegal in a @contextmanager generator and raises
        # RuntimeError: "generator didn't stop after throw()".
        log.warning("braintrust_span_failed", name=name, error=str(exc))
        raise


def _serialize_for_log(obj: Any) -> Any:
    """Convert objects to JSON-serializable form for Braintrust."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_log(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize_for_log(v) for k, v in obj.items()}
    if isinstance(obj, (str, int, float, bool)):
        return obj
    try:
        return json.loads(json.dumps(obj, default=str))
    except (TypeError, ValueError):
        return str(obj)
