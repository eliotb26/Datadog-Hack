"""
SIGNAL — Feedback Loop Data Models
Output schemas for Agent 5 (Meta-Agent) — one per self-improving loop.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Loop 1 — Campaign Performance → Prompt Weight Update
# ---------------------------------------------------------------------------

class PromptWeightUpdate(BaseModel):
    """A single prompt-weight change for one company + key."""

    company_id: str
    agent_name: str = "campaign_gen"
    weight_key: str = Field(
        ...,
        description=(
            "Short key describing what aspect of the prompt is being weighted, "
            "e.g. 'tone_aggressive', 'hook_question', 'cta_direct'."
        ),
    )
    weight_value: float = Field(
        ...,
        ge=0.0,
        le=3.0,
        description="Multiplier applied to this prompt element (1.0 = neutral).",
    )
    reasoning: str = Field(default="", description="Why this weight was set.")
    updated_at: datetime = Field(default_factory=_utcnow)

    def to_db_row(self) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "company_id": self.company_id,
            "agent_name": self.agent_name,
            "weight_key": self.weight_key,
            "weight_value": self.weight_value,
            "updated_at": self.updated_at.isoformat(),
        }


class Loop1Result(BaseModel):
    """Output of the Loop 1 sub-agent run."""

    company_id: str
    campaigns_analyzed: int = 0
    weight_updates: List[PromptWeightUpdate] = Field(default_factory=list)
    summary: str = ""
    success: bool = True
    error: Optional[str] = None
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Loop 2 — Cross-Company Style Learning
# ---------------------------------------------------------------------------

class SharedPattern(BaseModel):
    """A cross-company style pattern discovered by Loop 2."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_type: str = Field(
        ...,
        description="One of: style, timing, channel, signal.",
    )
    description: str = Field(
        ...,
        description="Human-readable description of the pattern.",
    )
    conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON: conditions under which this pattern applies.",
    )
    effect: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON: what the pattern predicts or causes.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in this pattern (based on sample size).",
    )
    sample_size: int = Field(
        default=0,
        description="Number of data points supporting this pattern.",
    )
    discovered_at: datetime = Field(default_factory=_utcnow)

    def to_db_row(self) -> dict:
        import json
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "conditions": json.dumps(self.conditions),
            "effect": json.dumps(self.effect),
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "discovered_at": self.discovered_at.isoformat(),
        }


class Loop2Result(BaseModel):
    """Output of the Loop 2 sub-agent run."""

    companies_analyzed: int = 0
    campaigns_in_sample: int = 0
    patterns_discovered: List[SharedPattern] = Field(default_factory=list)
    summary: str = ""
    success: bool = True
    error: Optional[str] = None
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Loop 3 — Signal Calibration
# ---------------------------------------------------------------------------

class CalibrationResult(BaseModel):
    """Signal-to-engagement calibration entry for Loop 3."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_category: str
    probability_threshold: float = Field(..., ge=0.0, le=1.0)
    volume_velocity_threshold: float = Field(default=0.0, ge=0.0)
    predicted_engagement: float = Field(..., ge=0.0)
    actual_engagement: float = Field(..., ge=0.0)
    accuracy_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How accurately this signal category predicted engagement (1 = perfect).",
    )
    company_type: str = ""
    calibrated_at: datetime = Field(default_factory=_utcnow)

    def to_db_row(self) -> dict:
        return {
            "id": self.id,
            "signal_category": self.signal_category,
            "probability_threshold": self.probability_threshold,
            "volume_velocity_threshold": self.volume_velocity_threshold,
            "predicted_engagement": self.predicted_engagement,
            "actual_engagement": self.actual_engagement,
            "accuracy_score": self.accuracy_score,
            "company_type": self.company_type,
            "calibrated_at": self.calibrated_at.isoformat(),
        }


class Loop3Result(BaseModel):
    """Output of the Loop 3 sub-agent run."""

    signal_pairs_analyzed: int = 0
    calibrations: List[CalibrationResult] = Field(default_factory=list)
    summary: str = ""
    success: bool = True
    error: Optional[str] = None
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Combined output of one full Agent 5 run
# ---------------------------------------------------------------------------

class FeedbackLoopResult(BaseModel):
    """Full output of one Agent 5 (Feedback Loop Agent) execution."""

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    loop1: Optional[Loop1Result] = None
    loop2: Optional[Loop2Result] = None
    loop3: Optional[Loop3Result] = None
    overall_summary: str = ""
    success: bool = True
    total_latency_ms: Optional[int] = None
    executed_at: datetime = Field(default_factory=_utcnow)
