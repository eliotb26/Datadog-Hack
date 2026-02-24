"""
Tests for Agent 4 — Distribution Routing Agent

Layers:
  Unit tests   : tools (score_channel_fit, get_optimal_posting_time, get_format_adaptation)
  Model tests  : CampaignConcept, ChannelScore, DistributionPlan Pydantic models
  Parse tests  : DistributionRoutingAgent._parse_response (JSON → DistributionPlan)
  Integration  : full ADK round-trip against live Gemini API
                 (skipped unless OPENROUTER_API_KEY is set)

Run all tests:
    pytest code/backend/tests/test_agent4.py -v

Run only fast (no API) tests:
    pytest code/backend/tests/test_agent4.py -v -m "not integration"

Run integration tests:
    pytest code/backend/tests/test_agent4.py -v -m integration
"""
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make sure the backend package is importable when running from repo root
# ---------------------------------------------------------------------------
_BACKEND = Path(__file__).parent.parent
if str(_BACKEND.parent) not in sys.path:
    sys.path.insert(0, str(_BACKEND.parent))

from backend.agents.distribution import (
    DistributionRoutingAgent,
    get_format_adaptation,
    get_optimal_posting_time,
    score_channel_fit,
)
from backend.models.campaign import CampaignConcept, Channel, ChannelScore, DistributionPlan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def b2b_campaign() -> CampaignConcept:
    """A realistic B2B SaaS campaign concept."""
    return CampaignConcept(
        id="camp-001",
        company_id="co-001",
        trend_signal_id="sig-001",
        headline="AI Prediction Markets Are Changing How B2B Teams Forecast",
        body_copy=(
            "Polymarket's probability on enterprise AI adoption hitting 70% by Q3 just crossed 0.82. "
            "B2B teams that ignore prediction markets are making decisions with one eye closed. "
            "SIGNAL surfaces these signals automatically so your marketing team always knows "
            "what's coming before the competition does. Start a free trial today."
        ),
        visual_direction="Dark gradient background, bold white typography, upward trend line graphic",
        confidence_score=0.82,
        channel_recommendation=Channel.LINKEDIN,
        channel_reasoning="Professional B2B audience aligns with LinkedIn.",
    )


@pytest.fixture
def consumer_campaign() -> CampaignConcept:
    """A consumer lifestyle campaign concept with a visual — Instagram-leaning."""
    return CampaignConcept(
        id="camp-002",
        company_id="co-002",
        headline="Summer Flavor Drop",
        body_copy="New. Fresh. Yours.",
        visual_direction="Bright citrus colors, lifestyle photography, bold sans-serif font",
        confidence_score=0.75,
        channel_recommendation=Channel.INSTAGRAM,
        channel_reasoning="Visual lifestyle content suits Instagram.",
    )


@pytest.fixture
def long_campaign() -> CampaignConcept:
    """A long-form campaign concept suited for a newsletter."""
    return CampaignConcept(
        id="camp-003",
        company_id="co-003",
        headline="Why Prediction Markets Beat Traditional Market Research",
        body_copy=" ".join(["word"] * 250),  # ~1250 chars
        visual_direction="Simple header graphic with chart",
        confidence_score=0.70,
        channel_recommendation=Channel.NEWSLETTER,
        channel_reasoning="Long-form analysis suits newsletter format.",
    )


@pytest.fixture
def b2b_company() -> dict:
    return {
        "id": "co-001",
        "name": "Acme SaaS",
        "industry": "B2B SaaS",
        "target_audience": "B2B enterprise CTOs and VP of Marketing",
        "tone_of_voice": "Professional and data-driven",
        "campaign_goals": "Lead generation and brand awareness",
    }


@pytest.fixture
def consumer_company() -> dict:
    return {
        "id": "co-002",
        "name": "FreshBev Co",
        "industry": "Consumer Beverages",
        "target_audience": "Young consumer lifestyle brand fans aged 18–34",
        "tone_of_voice": "Playful, energetic, and aspirational",
        "campaign_goals": "Brand awareness and direct-to-consumer sales",
    }


# ===========================================================================
# 1. TOOL UNIT TESTS
# ===========================================================================

class TestScoreChannelFit:
    """Tests for the score_channel_fit tool."""

    def test_linkedin_scores_high_for_b2b_medium_length(self, b2b_campaign: CampaignConcept):
        result = score_channel_fit(
            headline=b2b_campaign.headline,
            body_copy=b2b_campaign.body_copy,
            visual_direction=b2b_campaign.visual_direction or "",
            channel="linkedin",
            audience_type="B2B enterprise CTOs",
        )
        assert result["channel"] == "linkedin"
        assert result["audience_fit"] > 0.5, "B2B audience should score well on LinkedIn"
        assert "overall_fit" in result
        assert 0.0 <= result["overall_fit"] <= 1.0

    def test_instagram_penalizes_missing_visual(self, b2b_campaign: CampaignConcept):
        result_no_visual = score_channel_fit(
            headline=b2b_campaign.headline,
            body_copy=b2b_campaign.body_copy,
            visual_direction="",
            channel="instagram",
            audience_type="Consumer lifestyle brand",
        )
        result_with_visual = score_channel_fit(
            headline=b2b_campaign.headline,
            body_copy=b2b_campaign.body_copy,
            visual_direction="Bold hero image with product shot",
            channel="instagram",
            audience_type="Consumer lifestyle brand",
        )
        assert result_with_visual["visual_fit"] > result_no_visual["visual_fit"], (
            "Instagram should reward having a visual asset"
        )

    def test_twitter_penalizes_long_copy(self):
        long_copy = "A" * 1500
        result = score_channel_fit(
            headline="Headline",
            body_copy=long_copy,
            visual_direction="",
            channel="twitter",
            audience_type="Tech audience",
        )
        assert result["length_fit"] < 0.5, "Twitter should penalise 1500-char body copy"

    def test_newsletter_rewards_long_copy(self):
        long_copy = "word " * 200  # ~1000 chars
        result = score_channel_fit(
            headline="Headline",
            body_copy=long_copy,
            visual_direction="",
            channel="newsletter",
            audience_type="Engaged professional subscribers",
        )
        assert result["length_fit"] >= 0.8, "Newsletter should reward ~1000-char body"

    def test_all_scores_are_bounded(self, b2b_campaign: CampaignConcept):
        for channel in ["twitter", "linkedin", "instagram", "newsletter"]:
            result = score_channel_fit(
                headline=b2b_campaign.headline,
                body_copy=b2b_campaign.body_copy,
                visual_direction=b2b_campaign.visual_direction or "",
                channel=channel,
                audience_type="B2B professionals",
            )
            assert "error" not in result, f"Unexpected error for channel {channel}"
            for key in ("length_fit", "visual_fit", "audience_fit", "overall_fit"):
                assert 0.0 <= result[key] <= 1.0, f"{key} out of bounds for {channel}"

    def test_unknown_channel_returns_error(self, b2b_campaign: CampaignConcept):
        result = score_channel_fit(
            headline=b2b_campaign.headline,
            body_copy=b2b_campaign.body_copy,
            visual_direction="",
            channel="tiktok",
            audience_type="Gen Z consumers",
        )
        assert "error" in result


class TestGetOptimalPostingTime:
    """Tests for the get_optimal_posting_time tool."""

    def test_linkedin_returns_correct_days(self):
        result = get_optimal_posting_time("linkedin")
        assert "Tue" in result["day"] or "Thursday" in result["day"]
        assert result["channel"] == "linkedin"

    def test_newsletter_is_early_morning(self):
        result = get_optimal_posting_time("newsletter", timezone_hint="PT")
        assert "AM" in result["time_window"]
        assert result["timezone"] == "PT"

    def test_all_channels_return_full_recommendation(self):
        for channel in ["twitter", "linkedin", "instagram", "newsletter"]:
            result = get_optimal_posting_time(channel)
            assert "full_recommendation" in result
            assert len(result["full_recommendation"]) > 5

    def test_unknown_channel_returns_fallback(self):
        result = get_optimal_posting_time("snapchat")
        assert "full_recommendation" in result
        assert result["channel"] == "snapchat"


class TestGetFormatAdaptation:
    """Tests for the get_format_adaptation tool."""

    def test_instagram_requires_visual(self):
        result = get_format_adaptation("Headline", "Short copy", "", "instagram")
        assert result["visual_required"] is True

    def test_twitter_has_small_character_target(self):
        result = get_format_adaptation("Headline", "Some copy", "", "twitter")
        assert result["character_target"] <= 280

    def test_newsletter_has_large_character_target(self):
        result = get_format_adaptation("Headline", "Some copy", "", "newsletter")
        assert result["character_target"] >= 800

    def test_linkedin_does_not_require_visual(self):
        result = get_format_adaptation("Headline", "Some copy", "", "linkedin")
        assert result["visual_required"] is False

    def test_adaptation_notes_mention_body_length(self):
        body = "A" * 300
        result = get_format_adaptation("Headline", body, "", "twitter")
        assert "300" in result["adaptation_notes"]


# ===========================================================================
# 2. MODEL UNIT TESTS
# ===========================================================================

def _make_concept(**kwargs) -> CampaignConcept:
    """Helper: build a CampaignConcept with all required fields filled."""
    defaults = dict(
        company_id="co-1",
        headline="H",
        body_copy="Body copy text",
        visual_direction="Simple graphic",
        confidence_score=0.7,
        channel_recommendation=Channel.TWITTER,
        channel_reasoning="Default reasoning",
    )
    defaults.update(kwargs)
    return CampaignConcept(**defaults)


class TestCampaignConcept:
    def test_default_id_is_uuid(self):
        c = _make_concept()
        assert len(c.id) == 36  # UUID4 string length

    def test_confidence_score_is_bounded(self):
        with pytest.raises(Exception):
            _make_concept(confidence_score=1.5)

    def test_to_db_row_contains_required_keys(self, b2b_campaign: CampaignConcept):
        row = b2b_campaign.to_db_row()
        for key in ("id", "company_id", "headline", "body_copy", "confidence_score", "status"):
            assert key in row

    def test_from_db_row_round_trip(self, b2b_campaign: CampaignConcept):
        row = b2b_campaign.to_db_row()
        # from_db_row needs a created_at string
        if "created_at" not in row:
            row["created_at"] = datetime.now(UTC).isoformat()
        restored = CampaignConcept.from_db_row(row)
        assert restored.id == b2b_campaign.id
        assert restored.headline == b2b_campaign.headline
        assert restored.confidence_score == b2b_campaign.confidence_score


class TestDistributionPlan:
    def test_creation_with_all_fields(self):
        scores = [
            ChannelScore(channel="linkedin", fit_score=0.85, length_fit=0.9,
                         visual_fit=0.8, audience_fit=0.85, reasoning="B2B match"),
            ChannelScore(channel="twitter", fit_score=0.55, length_fit=0.4,
                         visual_fit=0.7, audience_fit=0.55, reasoning="Too long"),
        ]
        plan = DistributionPlan(
            campaign_id="camp-001",
            company_id="co-001",
            recommended_channel="linkedin",
            channel_scores=scores,
            posting_time="Tuesday 8–10 AM ET",
            format_adaptation="Expand to 1000 chars, professional tone",
            character_count_target=1000,
            visual_required=False,
            reasoning="LinkedIn best fits the B2B professional audience.",
            confidence=0.85,
        )
        assert plan.recommended_channel == "linkedin"
        assert len(plan.channel_scores) == 2

    def test_best_score_returns_correct_channel(self):
        scores = [
            ChannelScore(channel="linkedin", fit_score=0.85, length_fit=0.9,
                         visual_fit=0.8, audience_fit=0.85, reasoning="Best"),
            ChannelScore(channel="twitter", fit_score=0.55, length_fit=0.4,
                         visual_fit=0.7, audience_fit=0.55, reasoning="OK"),
        ]
        plan = DistributionPlan(
            campaign_id="c1", company_id="co1",
            recommended_channel="linkedin",
            channel_scores=scores,
            posting_time="Tue 8–10 AM ET",
            format_adaptation="...",
            reasoning="LinkedIn wins",
            confidence=0.85,
        )
        best = plan.best_score()
        assert best is not None
        assert best.channel == "linkedin"
        assert best.fit_score == 0.85

    def test_to_db_row_serializes_channel_scores_as_json(self):
        scores = [ChannelScore(channel="twitter", fit_score=0.6, length_fit=0.5,
                               visual_fit=0.7, audience_fit=0.6, reasoning="OK")]
        plan = DistributionPlan(
            campaign_id="c1", company_id="co1",
            recommended_channel="twitter",
            channel_scores=scores,
            posting_time="Mon 9–11 AM ET",
            format_adaptation="Keep it short",
            reasoning="Twitter fits",
            confidence=0.6,
        )
        row = plan.to_db_row()
        assert isinstance(row["channel_scores"], str)
        parsed = json.loads(row["channel_scores"])
        assert parsed[0]["channel"] == "twitter"


# ===========================================================================
# 3. RESPONSE PARSING TESTS  (no API calls — only tests _parse_response)
# ===========================================================================

class TestParseResponse:
    """Unit tests for DistributionRoutingAgent._parse_response."""

    @pytest.fixture
    def agent(self) -> DistributionRoutingAgent:
        """Create agent — constructor calls ADK but no API requests are made yet."""
        return DistributionRoutingAgent()

    @pytest.fixture
    def valid_json_response(self) -> str:
        return json.dumps({
            "recommended_channel": "linkedin",
            "channel_scores": [
                {"channel": "twitter",    "fit_score": 0.45, "length_fit": 0.3, "visual_fit": 0.7, "audience_fit": 0.5,  "reasoning": "Too long for Twitter"},
                {"channel": "linkedin",   "fit_score": 0.88, "length_fit": 0.9, "visual_fit": 0.8, "audience_fit": 0.95, "reasoning": "Strong B2B match"},
                {"channel": "instagram",  "fit_score": 0.35, "length_fit": 0.2, "visual_fit": 0.5, "audience_fit": 0.4,  "reasoning": "Wrong audience"},
                {"channel": "newsletter", "fit_score": 0.72, "length_fit": 0.8, "visual_fit": 0.7, "audience_fit": 0.65, "reasoning": "Good for long-form"},
            ],
            "posting_time": "Tuesday 8–10 AM ET",
            "format_adaptation": "Expand body to 1000 chars with a data-driven narrative. Max 3 hashtags.",
            "character_count_target": 1000,
            "visual_required": False,
            "reasoning": "LinkedIn scores 0.88 vs. the next best newsletter at 0.72. The professional B2B audience aligns perfectly.",
            "confidence": 0.88,
        })

    def test_valid_json_parses_correctly(self, agent, b2b_campaign, valid_json_response):
        plan = agent._parse_response(valid_json_response, b2b_campaign, "co-001")
        assert plan.recommended_channel == "linkedin"
        assert plan.confidence == 0.88
        assert len(plan.channel_scores) == 4
        assert plan.posting_time == "Tuesday 8–10 AM ET"
        assert plan.character_count_target == 1000
        assert plan.visual_required is False

    def test_json_embedded_in_prose_is_extracted(self, agent, b2b_campaign, valid_json_response):
        wrapped = f"After analysis, here is my recommendation:\n{valid_json_response}\nLet me know if you need anything."
        plan = agent._parse_response(wrapped, b2b_campaign, "co-001")
        assert plan.recommended_channel == "linkedin"

    def test_invalid_json_returns_fallback(self, agent, b2b_campaign):
        plan = agent._parse_response("Sorry, I cannot help with that.", b2b_campaign, "co-001")
        assert plan.campaign_id == b2b_campaign.id
        assert plan.recommended_channel == "linkedin"
        assert plan.confidence == 0.3  # fallback confidence

    def test_partial_json_uses_defaults(self, agent, b2b_campaign):
        partial = json.dumps({"recommended_channel": "twitter", "confidence": 0.6})
        plan = agent._parse_response(partial, b2b_campaign, "co-001")
        assert plan.recommended_channel == "twitter"
        assert plan.confidence == 0.6
        assert plan.channel_scores == []  # missing → empty list

    def test_campaign_id_is_preserved(self, agent, b2b_campaign, valid_json_response):
        plan = agent._parse_response(valid_json_response, b2b_campaign, "co-001")
        assert plan.campaign_id == b2b_campaign.id

    def test_company_id_is_preserved(self, agent, b2b_campaign, valid_json_response):
        plan = agent._parse_response(valid_json_response, b2b_campaign, "co-999")
        assert plan.company_id == "co-999"


# ===========================================================================
# 4. INTEGRATION TEST  (live API — skipped if no key)
# ===========================================================================

GEMINI_KEY_SET = bool(os.getenv("OPENROUTER_API_KEY", "").strip())


@pytest.fixture(autouse=True, scope="function")
def _rate_limit_guard(request):
    """Insert a 13-second cooldown between integration tests to respect the 5 req/min free tier."""
    if request.node.get_closest_marker("integration"):
        yield
        time.sleep(13)
    else:
        yield


@pytest.mark.integration
@pytest.mark.skipif(not GEMINI_KEY_SET, reason="OPENROUTER_API_KEY not set — skipping live API test")
class TestDistributionRoutingAgentIntegration:
    """
    Full end-to-end test: calls Gemini 2.5 Flash via ADK.
    Verifies the agent produces valid DistributionPlan objects for real campaigns.
    """

    @pytest.fixture
    def agent(self) -> DistributionRoutingAgent:
        return DistributionRoutingAgent()

    @pytest.mark.asyncio
    async def test_b2b_campaign_routes_to_linkedin_or_newsletter(
        self, agent, b2b_campaign, b2b_company
    ):
        plans = await agent.route_campaigns([b2b_campaign], b2b_company)
        assert len(plans) == 1
        plan = plans[0]

        assert plan.campaign_id == b2b_campaign.id
        assert plan.recommended_channel in ("twitter", "linkedin", "instagram", "newsletter")
        # B2B professional copy should strongly favour linkedin or newsletter
        assert plan.recommended_channel in ("linkedin", "newsletter"), (
            f"Expected linkedin or newsletter for B2B campaign, got {plan.recommended_channel}"
        )
        assert 0.0 <= plan.confidence <= 1.0
        assert len(plan.channel_scores) == 4
        assert plan.posting_time
        assert plan.format_adaptation
        assert plan.reasoning

    @pytest.mark.asyncio
    async def test_consumer_visual_campaign_routes_to_instagram(
        self, agent, consumer_campaign, consumer_company
    ):
        plans = await agent.route_campaigns([consumer_campaign], consumer_company)
        assert len(plans) == 1
        plan = plans[0]
        assert plan.recommended_channel in ("twitter", "linkedin", "instagram", "newsletter")
        assert plan.recommended_channel in ("instagram", "twitter"), (
            f"Expected instagram or twitter for consumer visual campaign, got {plan.recommended_channel}"
        )

    @pytest.mark.asyncio
    async def test_batch_routing_returns_one_plan_per_campaign(
        self, agent, b2b_campaign, consumer_campaign, b2b_company
    ):
        plans = await agent.route_campaigns(
            [b2b_campaign, consumer_campaign], b2b_company
        )
        assert len(plans) == 2
        assert plans[0].campaign_id == b2b_campaign.id
        assert plans[1].campaign_id == consumer_campaign.id

    @pytest.mark.asyncio
    async def test_plan_has_valid_structure(self, agent, b2b_campaign, b2b_company):
        plans = await agent.route_campaigns([b2b_campaign], b2b_company)
        plan = plans[0]

        # All channel scores present
        channels = {s.channel for s in plan.channel_scores}
        assert channels == {"twitter", "linkedin", "instagram", "newsletter"}

        # All fit scores in range
        for score in plan.channel_scores:
            assert 0.0 <= score.fit_score <= 1.0

    @pytest.mark.asyncio
    async def test_channel_history_accepted_without_error(
        self, agent, b2b_campaign, b2b_company
    ):
        history = {
            "linkedin": {"avg_engagement_rate": 0.045, "avg_impressions": 5000},
            "twitter": {"avg_engagement_rate": 0.012, "avg_impressions": 12000},
        }
        plans = await agent.route_campaigns([b2b_campaign], b2b_company, channel_history=history)
        assert len(plans) == 1
        assert plans[0].recommended_channel in ("twitter", "linkedin", "instagram", "newsletter")

