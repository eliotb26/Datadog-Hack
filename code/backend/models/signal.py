"""TrendSignal model — produced by Agent 2, consumed by Agent 3."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TrendSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    polymarket_market_id: str
    title: str
    category: Optional[str] = None
    probability: float = Field(default=0.5, ge=0.0, le=1.0)
    probability_momentum: float = Field(default=0.0, description="Rate of probability change")
    volume: float = Field(default=0.0, ge=0.0)
    volume_velocity: float = Field(default=0.0, description="24h volume / total volume ratio")
    relevance_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of company_id to relevance score (0.0-1.0)",
    )
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    surfaced_at: datetime = Field(default_factory=_utcnow)
    expires_at: Optional[datetime] = None

    def composite_score(self, company_id: str) -> float:
        """Combined score used for final ranking: volume velocity × relevance."""
        relevance = self.relevance_scores.get(company_id, 0.0)
        return (self.volume_velocity * 0.4) + (relevance * 0.4) + (self.probability_momentum * 0.2)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")
