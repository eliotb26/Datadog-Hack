"""
SIGNAL — Content Strategy & Content Piece Data Models
Output schemas for Agent 6 (Content Strategy) and Agent 7 (Content Production).
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ContentType(str, Enum):
    """All content formats the system can produce."""

    TWEET_THREAD = "tweet_thread"
    LINKEDIN_ARTICLE = "linkedin_article"
    BLOG_POST = "blog_post"
    VIDEO_SCRIPT = "video_script"
    INFOGRAPHIC = "infographic"
    NEWSLETTER = "newsletter"
    INSTAGRAM_CAROUSEL = "instagram_carousel"


CONTENT_TYPE_META: Dict[str, Dict[str, Any]] = {
    "tweet_thread": {
        "label": "Tweet Thread",
        "channel": "twitter",
        "typical_length": "3-8 tweets, each ≤280 chars",
        "visual_required": False,
    },
    "linkedin_article": {
        "label": "LinkedIn Article",
        "channel": "linkedin",
        "typical_length": "800-1500 words",
        "visual_required": False,
    },
    "blog_post": {
        "label": "Blog Post",
        "channel": "blog",
        "typical_length": "1000-2500 words",
        "visual_required": False,
    },
    "video_script": {
        "label": "Video Script",
        "channel": "youtube",
        "typical_length": "60-180 seconds spoken",
        "visual_required": True,
    },
    "infographic": {
        "label": "Infographic",
        "channel": "instagram",
        "typical_length": "5-8 data panels + copy",
        "visual_required": True,
    },
    "newsletter": {
        "label": "Newsletter",
        "channel": "email",
        "typical_length": "500-1000 words",
        "visual_required": False,
    },
    "instagram_carousel": {
        "label": "Instagram Carousel",
        "channel": "instagram",
        "typical_length": "5-10 slides with captions",
        "visual_required": True,
    },
}


class ContentStrategy(BaseModel):
    """Output of Agent 6 — a recommended content format for a campaign concept."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str = Field(..., description="CampaignConcept this strategy is for")
    company_id: str = Field(..., description="Owning company")

    content_type: ContentType = Field(..., description="Recommended content format")
    reasoning: str = Field(
        ..., description="Why this format was chosen for this campaign + audience"
    )
    target_length: str = Field(
        ..., description="Specific length guidance, e.g. '5-tweet thread' or '1200-word article'"
    )
    tone_direction: str = Field(
        ..., description="Specific tone adjustments for this format"
    )
    structure_outline: List[str] = Field(
        default_factory=list,
        description="High-level section/beat outline the production agent should follow",
    )
    priority_score: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Agent 6 confidence that this format will perform best",
    )
    visual_needed: bool = Field(
        default=False, description="Whether a visual asset is essential"
    )

    created_at: datetime = Field(default_factory=_utcnow)

    def to_db_row(self) -> dict:
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "company_id": self.company_id,
            "content_type": self.content_type.value,
            "reasoning": self.reasoning,
            "target_length": self.target_length,
            "tone_direction": self.tone_direction,
            "structure_outline": json.dumps(self.structure_outline),
            "priority_score": self.priority_score,
            "visual_needed": int(self.visual_needed),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "ContentStrategy":
        outline = row.get("structure_outline", "[]")
        if isinstance(outline, str):
            outline = json.loads(outline)
        return cls(
            id=row["id"],
            campaign_id=row["campaign_id"],
            company_id=row["company_id"],
            content_type=ContentType(row["content_type"]),
            reasoning=row.get("reasoning", ""),
            target_length=row.get("target_length", ""),
            tone_direction=row.get("tone_direction", ""),
            structure_outline=outline,
            priority_score=float(row.get("priority_score", 0.5)),
            visual_needed=bool(row.get("visual_needed", 0)),
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row.get("created_at")
                else _utcnow()
            ),
        )

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


class ContentPiece(BaseModel):
    """Output of Agent 7 — the actual generated content ready for review/publish."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = Field(..., description="ContentStrategy this was produced from")
    campaign_id: str = Field(..., description="Parent campaign")
    company_id: str = Field(..., description="Owning company")

    content_type: ContentType = Field(..., description="Format of this content piece")
    title: str = Field(..., description="Title / headline for the content")
    body: str = Field(
        ..., description="Full rendered content body (markdown for articles, JSON array for threads)"
    )
    summary: str = Field(
        default="", description="One-line summary of the content piece"
    )
    word_count: int = Field(default=0, description="Approximate word count")

    visual_prompt: Optional[str] = Field(
        default=None, description="Gemini image/video prompt for accompanying visual"
    )
    visual_asset_url: Optional[str] = Field(
        default=None, description="URL of the generated visual asset"
    )

    quality_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Self-assessed quality (Agent 7)"
    )
    brand_alignment: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Brand-voice alignment score"
    )

    status: str = "draft"
    created_at: datetime = Field(default_factory=_utcnow)

    def to_db_row(self) -> dict:
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "campaign_id": self.campaign_id,
            "company_id": self.company_id,
            "content_type": self.content_type.value,
            "title": self.title,
            "body": self.body,
            "summary": self.summary,
            "word_count": self.word_count,
            "visual_prompt": self.visual_prompt,
            "visual_asset_url": self.visual_asset_url,
            "quality_score": self.quality_score,
            "brand_alignment": self.brand_alignment,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "ContentPiece":
        return cls(
            id=row["id"],
            strategy_id=row["strategy_id"],
            campaign_id=row["campaign_id"],
            company_id=row["company_id"],
            content_type=ContentType(row["content_type"]),
            title=row["title"],
            body=row["body"],
            summary=row.get("summary", ""),
            word_count=int(row.get("word_count", 0)),
            visual_prompt=row.get("visual_prompt"),
            visual_asset_url=row.get("visual_asset_url"),
            quality_score=float(row.get("quality_score", 0)),
            brand_alignment=float(row.get("brand_alignment", 0)),
            status=row.get("status", "draft"),
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row.get("created_at")
                else _utcnow()
            ),
        )

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


class ContentStrategyRequest(BaseModel):
    """Input to Agent 6."""

    campaign_id: str
    company_id: str
    headline: str
    body_copy: str
    channel_recommendation: str
    target_audience: str = ""
    campaign_goals: str = ""
    tone_of_voice: str = ""


class ContentStrategyResponse(BaseModel):
    """Output from Agent 6."""

    campaign_id: str
    strategies: List[ContentStrategy]
    latency_ms: Optional[int] = None
    success: bool = True


class ContentProductionRequest(BaseModel):
    """Input to Agent 7."""

    strategy: ContentStrategy
    campaign_headline: str
    campaign_body_copy: str
    company_name: str = ""
    tone_of_voice: str = ""
    target_audience: str = ""
    campaign_goals: str = ""


class ContentProductionResponse(BaseModel):
    """Output from Agent 7."""

    strategy_id: str
    pieces: List[ContentPiece]
    latency_ms: Optional[int] = None
    success: bool = True
