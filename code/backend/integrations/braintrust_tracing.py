from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Dict, Optional


class TracedRun(AbstractContextManager["TracedRun"]):
    """No-op tracing context used when sponsor tracing is disabled."""

    def __init__(self, name: str, input: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.input = input or {}

    def __enter__(self) -> "TracedRun":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def log_output(
        self,
        output: Optional[Dict[str, Any]] = None,
        scores: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        return None


def score_campaign_concept(concept: Any) -> float:
    return float(getattr(concept, "confidence_score", 0.0) or 0.0)


def score_brand_alignment(concept: Any, company: Any) -> float:
    return float(getattr(concept, "confidence_score", 0.0) or 0.0)


def score_distribution_plan(plan: Any) -> float:
    return float(getattr(plan, "confidence_score", 0.0) or 0.0)
