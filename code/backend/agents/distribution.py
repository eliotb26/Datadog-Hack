"""
SIGNAL — Agent 4: Distribution Routing Agent

Purpose  : Score campaign concepts for channel fit and produce posting recommendations.
Input    : CampaignConcept[] + company profile + optional channel performance history
Output   : DistributionPlan[] — one plan per campaign concept

LLM      : gemini-2.5-flash  (classification task, lower complexity)
ADK      : LlmAgent with 3 FunctionTools + channel knowledge base in system instruction
"""
import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import Any, Optional

import structlog
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types as genai_types

from ..config import settings
from ..integrations.braintrust_tracing import TracedRun, score_distribution_plan
from ..models.campaign import CampaignConcept, ChannelScore, DistributionPlan  # noqa: F401

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Channel knowledge base  (embedded as part of the system instruction)
# ---------------------------------------------------------------------------

_CHANNEL_KNOWLEDGE = """
## Channel Distribution Matrix

### Twitter/X
- Post Length  : Short, ≤280 characters. Threads extend this but the hook must land in char 1–280.
- Visual Weight: Low–Medium. Text-first posts are common; images boost engagement ~2×.
- Audience     : Broad, tech community, crypto/finance, breaking news, real-time discussions.
- Best Timing  : 9–11 AM and 7–9 PM in the target timezone (weekdays). Avoid Sundays.
- Tone         : Punchy, conversational, hook-first. Questions, bold claims, or hot takes.
- Format       : Hook tweet → thread or standalone. Max 1–2 hashtags. CTA at end.

### LinkedIn
- Post Length  : Medium, 500–1 500 characters. Longer posts (1 200+) work well if story-driven.
- Visual Weight: Low. Thought-leadership text posts outperform image-only posts.
- Audience     : B2B professionals, executives, hiring managers, industry insiders.
- Best Timing  : Tue–Thu 8–10 AM. Avoid weekends.
- Tone         : Professional, authoritative, insight-led. Personal stories perform very well.
- Format       : Hook line → story/insight → key takeaway → CTA. Max 3 hashtags.

### Instagram
- Post Length  : Caption 100–150 characters optimal. Visual is primary; caption is secondary.
- Visual Weight: High. A visual asset is required.
- Audience     : Consumer brands, lifestyle, B2C, younger demographics (18–34).
- Best Timing  : Mon–Fri 12–2 PM. Wednesday is the peak day.
- Tone         : Aspirational, visual storytelling, lifestyle. Emojis welcome.
- Format       : Strong hero image/video → short punchy caption → CTA → 10–15 hashtags.

### Newsletter
- Post Length  : Long-form, 800–1 500 words. Readers opted in for depth.
- Visual Weight: Medium. Headers, images, and callout boxes aid readability.
- Audience     : Highly engaged opted-in subscribers. Highest trust and purchase intent.
- Best Timing  : Tuesday or Thursday, 6–9 AM.
- Tone         : Educational, personal, high-value. Address reader as "you".
- Format       : Subject line → preview text → personal hook → sections → CTA.
"""

# ---------------------------------------------------------------------------
# Tool 1 — rule-based channel fit scorer
# ---------------------------------------------------------------------------

def score_channel_fit(
    headline: str,
    body_copy: str,
    visual_direction: str,
    channel: str,
    audience_type: str,
) -> dict:
    """
    Compute a rule-based fit score for a campaign concept against a specific channel.

    Args:
        headline: Campaign headline text.
        body_copy: Campaign body copy (the text that will be posted).
        visual_direction: Notes describing any visual asset or '' if none.
        channel: Target channel — one of: twitter, linkedin, instagram, newsletter.
        audience_type: Brand's target audience descriptor from the company profile.

    Returns:
        dict with keys: channel, length_fit, visual_fit, audience_fit, overall_fit,
        body_length, has_visual.  All fit values are 0.0–1.0.
    """
    _CHANNEL_SPECS: dict[str, dict] = {
        "twitter": {
            "ideal_length": 240,
            "max_length": 800,
            "visual_weight": "low_medium",
            "audience_keywords": ["broad", "tech", "developer", "consumer", "b2c", "startup"],
        },
        "linkedin": {
            "ideal_length": 1000,
            "max_length": 1500,
            "visual_weight": "low",
            "audience_keywords": ["b2b", "professional", "enterprise", "cto", "manager", "executive", "saas"],
        },
        "instagram": {
            "ideal_length": 150,
            "max_length": 300,
            "visual_weight": "high",
            "audience_keywords": ["consumer", "lifestyle", "b2c", "young", "brand", "fashion", "food"],
        },
        "newsletter": {
            "ideal_length": 1200,
            "max_length": 2000,
            "visual_weight": "medium",
            "audience_keywords": ["engaged", "subscriber", "reader", "professional", "b2b", "b2c", "niche"],
        },
    }

    ch = _CHANNEL_SPECS.get(channel.lower())
    if not ch:
        return {"error": f"Unknown channel '{channel}'. Use twitter, linkedin, instagram, or newsletter."}

    body_len = len(body_copy)
    has_visual = bool(visual_direction and visual_direction.strip())
    audience_lower = audience_type.lower()

    # --- Length fit ---
    ideal = ch["ideal_length"]
    max_len = ch["max_length"]
    if body_len <= ideal:
        length_fit = 1.0
    elif body_len <= max_len:
        length_fit = round(1.0 - ((body_len - ideal) / (max_len - ideal)) * 0.5, 3)
    else:
        length_fit = max(0.1, round(0.5 - ((body_len - max_len) / max_len) * 0.4, 3))

    # --- Visual fit ---
    weight = ch["visual_weight"]
    if weight == "high":
        visual_fit = 1.0 if has_visual else 0.15
    elif weight == "low":
        visual_fit = 0.65 if has_visual else 1.0
    else:  # low_medium or medium
        visual_fit = 0.85 if has_visual else 0.75

    # --- Audience fit ---
    kw_matches = sum(1 for kw in ch["audience_keywords"] if kw in audience_lower)
    audience_fit = round(min(1.0, 0.4 + kw_matches * 0.15), 3)

    overall = round((length_fit + visual_fit + audience_fit) / 3, 3)

    return {
        "channel": channel,
        "length_fit": length_fit,
        "visual_fit": visual_fit,
        "audience_fit": audience_fit,
        "overall_fit": overall,
        "body_length": body_len,
        "has_visual": has_visual,
    }


# ---------------------------------------------------------------------------
# Tool 2 — optimal posting time lookup
# ---------------------------------------------------------------------------

def get_optimal_posting_time(channel: str, timezone_hint: str = "ET") -> dict:
    """
    Return the optimal posting time window for a given channel.

    Args:
        channel: Target channel — twitter, linkedin, instagram, or newsletter.
        timezone_hint: Audience timezone abbreviation, e.g. ET, PT, UTC.

    Returns:
        dict with keys: channel, day, time_window, timezone, reasoning.
    """
    _SCHEDULES: dict[str, dict] = {
        "twitter": {
            "day": "Weekdays (Mon–Fri)",
            "time_window": "9–11 AM or 7–9 PM",
            "reasoning": "Peak engagement windows for real-time feed scrolling.",
        },
        "linkedin": {
            "day": "Tuesday–Thursday",
            "time_window": "8–10 AM",
            "reasoning": "Professionals check feed early before meetings; mid-week outperforms Mon/Fri.",
        },
        "instagram": {
            "day": "Monday–Friday (Wednesday peak)",
            "time_window": "12–2 PM",
            "reasoning": "Lunch-hour browsing peak; Wednesday shows highest reach industry-wide.",
        },
        "newsletter": {
            "day": "Tuesday or Thursday",
            "time_window": "6–9 AM",
            "reasoning": "Early-morning sends are read before the work day starts.",
        },
    }

    schedule = _SCHEDULES.get(channel.lower(), {
        "day": "Weekdays",
        "time_window": "9–11 AM",
        "reasoning": "Default business-hours recommendation.",
    })

    return {
        "channel": channel,
        "day": schedule["day"],
        "time_window": schedule["time_window"],
        "timezone": timezone_hint,
        "full_recommendation": f"{schedule['day']}, {schedule['time_window']} {timezone_hint}",
        "reasoning": schedule["reasoning"],
    }


# ---------------------------------------------------------------------------
# Tool 3 — format adaptation notes generator
# ---------------------------------------------------------------------------

def get_format_adaptation(
    headline: str,
    body_copy: str,
    visual_direction: str,
    channel: str,
) -> dict:
    """
    Generate specific format adaptation instructions to tailor a campaign for a channel.

    Args:
        headline: Original campaign headline.
        body_copy: Original campaign body copy.
        visual_direction: Original visual direction notes, or '' if none.
        channel: Target channel — twitter, linkedin, instagram, or newsletter.

    Returns:
        dict with keys: channel, character_target, visual_required, adaptation_notes.
    """
    body_len = len(body_copy)

    _ADAPTATIONS: dict[str, dict] = {
        "twitter": {
            "character_target": 240,
            "visual_required": False,
            "adaptation_notes": (
                f"Compress to a punchy hook ≤240 chars. "
                f"Current body is {body_len} chars — extract the single boldest claim. "
                "End with a question or CTA. Add 1–2 relevant hashtags. "
                "Consider a thread if the full message requires more space."
            ),
        },
        "linkedin": {
            "character_target": 1000,
            "visual_required": False,
            "adaptation_notes": (
                f"Expand headline into a thought-leadership opening line. "
                f"Body copy at {body_len} chars — target 800–1 200 chars with a structured narrative. "
                "Open with a bold insight, support with 2–3 data points or observations, "
                "close with a CTA. Max 3 hashtags."
            ),
        },
        "instagram": {
            "character_target": 150,
            "visual_required": True,
            "adaptation_notes": (
                f"A visual asset is required — create one from the visual direction notes. "
                f"Caption should be 100–150 chars (currently {body_len}). "
                "Use aspirational, emotion-driven language. "
                "Add 10–15 hashtags in the first comment, not the caption."
            ),
        },
        "newsletter": {
            "character_target": 1500,
            "visual_required": False,
            "adaptation_notes": (
                f"Expand into a long-form section (800–1 500 words). "
                f"Current body is {body_len} chars — add context, supporting data, "
                "and real-world examples. Structure with H2 subheadings. "
                "Include a clear summary and a single CTA at the end."
            ),
        },
    }

    ch = _ADAPTATIONS.get(channel.lower(), {
        "character_target": 500,
        "visual_required": False,
        "adaptation_notes": f"Adapt the {body_len}-char body copy for {channel} format conventions.",
    })

    return {"channel": channel, **ch}


# ---------------------------------------------------------------------------
# Agent 4 — DistributionRoutingAgent
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = f"""You are the Distribution Routing specialist for SIGNAL, an AI content intelligence platform.

Your responsibility is to analyze each campaign concept and determine:
1. The optimal distribution channel (twitter, linkedin, instagram, or newsletter)
2. The best posting time window
3. How to adapt the campaign copy for that channel's format

## Process (follow this order)
For EACH campaign you receive:
1. Call `score_channel_fit` for ALL FOUR channels (twitter, linkedin, instagram, newsletter).
2. Call `get_optimal_posting_time` for the channel with the highest overall_fit score.
3. Call `get_format_adaptation` for the recommended channel.
4. Synthesize the tool outputs into a distribution recommendation.

## Channel Reference
{_CHANNEL_KNOWLEDGE}

## Output Format
After calling all tools, return a single JSON object (no markdown, no explanation outside the JSON):

{{
  "recommended_channel": "twitter|linkedin|instagram|newsletter",
  "channel_scores": [
    {{"channel": "twitter",    "fit_score": 0.0, "length_fit": 0.0, "visual_fit": 0.0, "audience_fit": 0.0, "reasoning": "one sentence"}},
    {{"channel": "linkedin",   "fit_score": 0.0, "length_fit": 0.0, "visual_fit": 0.0, "audience_fit": 0.0, "reasoning": "one sentence"}},
    {{"channel": "instagram",  "fit_score": 0.0, "length_fit": 0.0, "visual_fit": 0.0, "audience_fit": 0.0, "reasoning": "one sentence"}},
    {{"channel": "newsletter", "fit_score": 0.0, "length_fit": 0.0, "visual_fit": 0.0, "audience_fit": 0.0, "reasoning": "one sentence"}}
  ],
  "posting_time": "from get_optimal_posting_time full_recommendation field",
  "format_adaptation": "from get_format_adaptation adaptation_notes field",
  "character_count_target": 0,
  "visual_required": false,
  "reasoning": "2–3 sentences explaining why you chose this channel over the alternatives.",
  "confidence": 0.0
}}

Use ONLY the tool outputs to populate these fields — do NOT invent data.
confidence should reflect how clear-cut the channel choice is (0.9+ = obvious winner, 0.5 = borderline).
"""


class DistributionRoutingAgent:
    """
    Agent 4 — Distribution Routing Agent.

    Uses Gemini 2.5 Flash via Google ADK to score campaign concepts against
    four channels and produce a DistributionPlan for each.

    Usage:
        agent = DistributionRoutingAgent()
        plans = await agent.route_campaigns(campaigns, company_profile)
    """

    MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    AGENT_NAME = "distribution_routing"
    APP_NAME = "signal"

    def __init__(self) -> None:
        self._session_service = InMemorySessionService()
        self._adk_agent = LlmAgent(
            name=self.AGENT_NAME,
            model=self.MODEL,
            instruction=_SYSTEM_INSTRUCTION,
            tools=[
                FunctionTool(score_channel_fit),
                FunctionTool(get_optimal_posting_time),
                FunctionTool(get_format_adaptation),
            ],
        )
        self._runner = Runner(
            app_name=self.APP_NAME,
            agent=self._adk_agent,
            session_service=self._session_service,
        )
        logger.info("distribution_routing_agent_initialized", model=self.MODEL)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def route_campaigns(
        self,
        campaigns: list[CampaignConcept],
        company_profile: dict[str, Any],
        channel_history: Optional[dict[str, Any]] = None,
    ) -> list[DistributionPlan]:
        """
        Route a batch of campaign concepts to optimal channels.

        Args:
            campaigns: CampaignConcept list from Agent 3.
            company_profile: Dict with keys: id, name, industry, target_audience,
                             tone_of_voice, campaign_goals.
            channel_history: Optional dict mapping channel names to historical
                             engagement metrics (used as context hints).

        Returns:
            List of DistributionPlan objects, one per campaign.
        """
        bt_input = {
            "company_id": company_profile.get("id", ""),
            "company_name": company_profile.get("name", ""),
            "n_campaigns": len(campaigns),
            "campaign_headlines": [c.headline for c in campaigns],
        }

        with TracedRun("distribution", input=bt_input) as bt_span:
            try:
                plans: list[DistributionPlan] = []
                for campaign in campaigns:
                    plan = await self._route_single(campaign, company_profile, channel_history or {})
                    plans.append(plan)

                if plans:
                    channel_scores = [score_distribution_plan(p) for p in plans]
                    bt_span.log_output(
                        output={
                            "plans": [
                                {
                                    "campaign_id": p.campaign_id,
                                    "recommended_channel": p.recommended_channel,
                                    "confidence": p.confidence,
                                }
                                for p in plans
                            ],
                            "count": len(plans),
                        },
                        scores={
                            "channel_fit": sum(channel_scores) / len(channel_scores)
                            if channel_scores
                            else 0,
                        },
                        metadata={"n_plans": len(plans)},
                    )
            except asyncio.CancelledError:
                logger.warning(
                    "distribution_agent_cancelled",
                    company_id=company_profile.get("id", ""),
                    plans_completed=len(plans),
                    plans_requested=len(campaigns),
                )
                raise

        return plans

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _route_single(
        self,
        campaign: CampaignConcept,
        company_profile: dict[str, Any],
        channel_history: dict[str, Any],
    ) -> DistributionPlan:
        """Run a single campaign through the ADK agent and return a DistributionPlan."""
        start_ms = time.time()
        session_id = str(uuid.uuid4())

        await self._session_service.create_session(
            app_name=self.APP_NAME,
            user_id="system",
            session_id=session_id,
        )

        user_message = self._build_user_message(campaign, company_profile, channel_history)

        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=user_message)],
        )

        final_text = ""
        async for event in self._runner.run_async(
            user_id="system",
            session_id=session_id,
            new_message=content,
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_text += part.text

        latency_ms = int((time.time() - start_ms) * 1000)
        plan = self._parse_response(final_text, campaign, company_profile.get("id", ""))

        logger.info(
            "distribution_plan_created",
            campaign_id=campaign.id,
            recommended_channel=plan.recommended_channel,
            confidence=plan.confidence,
            latency_ms=latency_ms,
        )
        return plan

    def _build_user_message(
        self,
        campaign: CampaignConcept,
        company_profile: dict[str, Any],
        channel_history: dict[str, Any],
    ) -> str:
        history_block = ""
        if channel_history:
            history_block = (
                "\n\n## Channel Performance History (use as additional context)\n"
                + json.dumps(channel_history, indent=2)
            )

        return f"""Route this campaign concept to the optimal distribution channel.

## Company
- Name           : {company_profile.get('name', 'Unknown')}
- Industry       : {company_profile.get('industry', 'Unknown')}
- Target Audience: {company_profile.get('target_audience', 'General audience')}
- Brand Tone     : {company_profile.get('tone_of_voice', 'Professional')}
- Goals          : {company_profile.get('campaign_goals', 'Engagement and brand awareness')}

## Campaign Concept (ID: {campaign.id})
- Headline       : {campaign.headline}
- Body Copy      : {campaign.body_copy}
- Visual Notes   : {campaign.visual_direction or 'None specified'}
- Agent 3 Score  : {campaign.confidence_score}
- Agent 3 Channel: {campaign.channel_recommendation or 'Not specified'}{history_block}

Score this campaign against all four channels using score_channel_fit, then recommend
the best one with timing and format adaptation notes. Return only the JSON object."""

    def _parse_response(
        self,
        response_text: str,
        campaign: CampaignConcept,
        company_id: str,
    ) -> DistributionPlan:
        """Parse the LLM JSON response into a DistributionPlan, with a safe fallback."""
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                channel_scores = [
                    ChannelScore(
                        channel=s.get("channel", "unknown"),
                        fit_score=float(s.get("fit_score", 0.5)),
                        length_fit=float(s.get("length_fit", 0.5)),
                        visual_fit=float(s.get("visual_fit", 0.5)),
                        audience_fit=float(s.get("audience_fit", 0.5)),
                        reasoning=s.get("reasoning", ""),
                    )
                    for s in data.get("channel_scores", [])
                ]
                return DistributionPlan(
                    campaign_id=campaign.id,
                    company_id=company_id,
                    recommended_channel=data.get("recommended_channel", "linkedin"),
                    channel_scores=channel_scores,
                    posting_time=data.get("posting_time", "Tuesday 8–10 AM ET"),
                    format_adaptation=data.get("format_adaptation", ""),
                    character_count_target=data.get("character_count_target"),
                    visual_required=bool(data.get("visual_required", False)),
                    reasoning=data.get("reasoning", ""),
                    confidence=float(data.get("confidence", 0.5)),
                )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
                logger.warning("distribution_parse_failed", error=str(exc), raw=response_text[:200])

        # Safe fallback — never crash, always return something usable
        return DistributionPlan(
            campaign_id=campaign.id,
            company_id=company_id,
            recommended_channel="linkedin",
            channel_scores=[],
            posting_time="Tuesday 8–10 AM ET",
            format_adaptation=(
                "Adapt for LinkedIn: expand to 800–1 200 chars, professional tone, "
                "3 hashtags max, close with a clear CTA."
            ),
            character_count_target=1000,
            visual_required=False,
            reasoning="Defaulted to LinkedIn as a safe professional channel. Manual review recommended.",
            confidence=0.3,
        )
