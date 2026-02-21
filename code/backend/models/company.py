"""
onlyGen — CompanyProfile Data Model
The output schema of Agent 1 (Brand Intake Agent).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    """Structured brand profile created by Agent 1."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Full company/brand name")
    industry: str = Field(..., description="Industry vertical (e.g., SaaS, e-commerce, fintech)")
    website: Optional[str] = Field(default=None, description="Company website URL (domain)")
    tone_of_voice: Optional[str] = Field(
        default=None,
        description="Brand voice descriptor"
    )
    target_audience: Optional[str] = Field(
        default=None,
        description="Primary audience description"
    )
    campaign_goals: Optional[str] = Field(
        default=None,
        description="Primary marketing objectives"
    )
    competitors: List[str] = Field(default_factory=list)
    content_history: List[str] = Field(default_factory=list)
    visual_style: Optional[str] = None
    safety_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_db_row(self) -> dict:
        """Convert to flat dict for SQLite insertion."""
        return {
            "id": self.id,
            "name": self.name,
            "industry": self.industry,
            "website": self.website,
            "tone_of_voice": self.tone_of_voice,
            "target_audience": self.target_audience,
            "campaign_goals": self.campaign_goals,
            "competitors": json.dumps(self.competitors),
            "content_history": json.dumps(self.content_history),
            "visual_style": self.visual_style,
            "safety_threshold": self.safety_threshold,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "CompanyProfile":
        """Reconstruct from a SQLite row dict."""
        return cls(
            id=row["id"],
            name=row["name"],
            industry=row["industry"],
            website=row.get("website"),
            tone_of_voice=row.get("tone_of_voice"),
            target_audience=row.get("target_audience"),
            campaign_goals=row.get("campaign_goals"),
            competitors=json.loads(row.get("competitors") or "[]"),
            content_history=json.loads(row.get("content_history") or "[]"),
            visual_style=row.get("visual_style"),
            safety_threshold=float(row.get("safety_threshold") or 0.7),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def to_prompt_context(self) -> str:
        """Serialise profile into a compact string for LLM prompts (campaign_gen, trend_intel, etc.)."""
        parts = [
            f"Company: {self.name}",
            f"Industry: {self.industry}",
        ]
        if self.website:
            parts.append(f"Website: {self.website}")
        if self.tone_of_voice:
            parts.append(f"Tone: {self.tone_of_voice}")
        if self.target_audience:
            parts.append(f"Audience: {self.target_audience}")
        if self.campaign_goals:
            parts.append(f"Goals: {self.campaign_goals}")
        if self.competitors:
            parts.append(f"Competitors: {', '.join(self.competitors)}")
        return "\n".join(parts)


class CompanyProfileInput(BaseModel):
    """Raw intake form submitted by the user — Agent 1 enriches this into CompanyProfile."""
    name: str
    industry: str
    website: Optional[str] = Field(default=None, description="Company website URL; if set, content may be fetched and used as context")
    tone_of_voice: Optional[str] = None
    target_audience: Optional[str] = None
    campaign_goals: Optional[str] = None
    competitors: Optional[List[str]] = None
    content_history: Optional[List[str]] = None
    visual_style: Optional[str] = None
    safety_threshold: Optional[float] = None
    description: Optional[str] = Field(
        default=None,
        description="Free-text brand description — Agent 1 extracts structure from this if fields are missing"
    )
