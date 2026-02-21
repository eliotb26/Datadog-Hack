"""
Company profile and brand intake API.

POST /api/company/intake
    Submit brand profile (form + optional website). If website is provided,
    we fetch the page and use its content to enrich the profile via the Brand Intake Agent.

GET /api/company/profile
    Return the most recently saved company profile (if any).

POST /api/company/fetch-website
    Fetch a URL and return extracted text only (for "preview" or pre-fill without saving).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.brand_intake import run_brand_intake
from backend.database import get_company_by_id, get_latest_company_row
from backend.integrations.website_fetch import fetch_website_text
from backend.models.company import CompanyProfile, CompanyProfileInput
import backend.database as db_module

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/company", tags=["company"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class CompanyIntakeRequest(BaseModel):
    """Payload for saving or creating a company profile (matches Settings form)."""
    companyName: str = Field(..., min_length=1, description="Company name")
    website: Optional[str] = Field(default=None, description="Company website URL; we will fetch and use content to enrich the profile")
    industry: str = Field(..., min_length=1, description="Industry")
    description: Optional[str] = Field(default=None, description="Free-text company description")
    audience: Optional[str] = Field(default=None, description="Target audience")
    tone: Optional[str] = Field(default=None, description="Tone of voice")
    goals: Optional[str] = Field(default=None, description="Campaign goals")
    avoidTopics: Optional[str] = Field(default=None, description="Topics to avoid")
    # Optional structured fields
    competitors: Optional[list[str]] = None
    content_history: Optional[list[str]] = None
    visual_style: Optional[str] = None


class CompanyIntakeResponse(BaseModel):
    """Response after running brand intake."""
    success: bool
    company_id: Optional[str] = None
    agent_response: Optional[str] = None
    latency_ms: Optional[int] = None
    message: Optional[str] = None


class FetchWebsiteRequest(BaseModel):
    url: str = Field(..., min_length=1)


class FetchWebsiteResponse(BaseModel):
    success: bool
    text: Optional[str] = None
    message: Optional[str] = None


def _company_profile_to_api(profile: CompanyProfile) -> dict[str, Any]:
    """Convert CompanyProfile to JSON-safe dict for API response."""
    return {
        "id": profile.id,
        "name": profile.name,
        "industry": profile.industry,
        "website": profile.website,
        "tone_of_voice": profile.tone_of_voice,
        "target_audience": profile.target_audience,
        "campaign_goals": profile.campaign_goals,
        "competitors": profile.competitors,
        "content_history": profile.content_history,
        "visual_style": profile.visual_style,
        "safety_threshold": profile.safety_threshold,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/intake", response_model=CompanyIntakeResponse)
async def company_intake(req: CompanyIntakeRequest) -> CompanyIntakeResponse:
    """
    Create or update a company profile using the Brand Intake Agent.
    If `website` is provided, we fetch the URL and pass its content to the agent
    so it can infer name, industry, audience, goals, etc. from the site.
    """
    website_context: Optional[str] = None
    if req.website and req.website.strip():
        website_context = await fetch_website_text(req.website.strip())
        if website_context:
            log.info("Fetched website context for %s (%d chars)", req.website, len(website_context))
        else:
            log.warning("Could not fetch website content for %s", req.website)

    # Build free-text description from form (and optionally website content)
    description_parts = []
    if req.description and req.description.strip():
        description_parts.append(req.description.strip())
    if req.audience and req.audience.strip():
        description_parts.append(f"Target audience: {req.audience.strip()}")
    if req.tone and req.tone.strip():
        description_parts.append(f"Tone of voice: {req.tone.strip()}")
    if req.goals and req.goals.strip():
        description_parts.append(f"Campaign goals: {req.goals.strip()}")
    if req.avoidTopics and req.avoidTopics.strip():
        description_parts.append(f"Topics to avoid: {req.avoidTopics.strip()}")
    description = "\n\n".join(description_parts) if description_parts else None

    intake = CompanyProfileInput(
        name=req.companyName.strip(),
        industry=req.industry.strip(),
        website=req.website.strip() if req.website else None,
        tone_of_voice=req.tone or None,
        target_audience=req.audience or None,
        campaign_goals=req.goals or None,
        competitors=req.competitors,
        content_history=req.content_history,
        visual_style=req.visual_style,
        description=description,
    )

    try:
        result = await run_brand_intake(
            intake,
            website_context=website_context,
        )
    except Exception as e:
        log.exception("Brand intake failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return CompanyIntakeResponse(
        success=result["success"],
        company_id=result.get("company_id"),
        agent_response=result.get("agent_response"),
        latency_ms=result.get("latency_ms"),
        message=result.get("agent_response") if result.get("success") else "Profile could not be saved; check required fields.",
    )


@router.get("/profile")
async def get_latest_profile() -> dict[str, Any]:
    """Return the most recently updated company profile, if any."""
    row = await get_latest_company_row(db_module.DB_PATH)
    if not row:
        raise HTTPException(status_code=404, detail="No company profile found")
    profile = CompanyProfile.from_db_row(row)
    return _company_profile_to_api(profile)


@router.get("/profile/{company_id}")
async def get_profile_by_id(company_id: str) -> dict[str, Any]:
    """Return a company profile by ID. Used by campaign/trend pipelines that need to load the active company."""
    row = await get_company_by_id(company_id, db_module.DB_PATH)
    if not row:
        raise HTTPException(status_code=404, detail=f"No company profile found for id={company_id}")
    profile = CompanyProfile.from_db_row(row)
    return _company_profile_to_api(profile)


@router.post("/fetch-website", response_model=FetchWebsiteResponse)
async def fetch_website(req: FetchWebsiteRequest) -> FetchWebsiteResponse:
    """Fetch a URL and return extracted text (for preview or pre-fill)."""
    text = await fetch_website_text(req.url)
    if text is None:
        return FetchWebsiteResponse(success=False, message="Could not fetch or extract text from the URL")
    return FetchWebsiteResponse(success=True, text=text)
