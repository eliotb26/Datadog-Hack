"""
Tests for Braintrust tracing integration.

Layers:
  Unit tests   : score_campaign_concept, score_brand_alignment, score_distribution_plan
  Unit tests   : TracedRun with mocked Logger (no network)
  Integration  : live trace to Braintrust (requires BRAINTRUST_API_KEY)

Run all tests:
    pytest code/backend/tests/test_braintrust_tracing.py -v

Run only fast (no API) tests:
    pytest code/backend/tests/test_braintrust_tracing.py -v -m "not integration"

Run integration tests:
    pytest code/backend/tests/test_braintrust_tracing.py -v -m integration
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make sure the backend package is importable when running from repo root
# ---------------------------------------------------------------------------
_BACKEND = Path(__file__).parent.parent
if str(_BACKEND.parent) not in sys.path:
    sys.path.insert(0, str(_BACKEND.parent))

from backend.integrations.braintrust_tracing import (
    TracedRun,
    get_logger,
    score_brand_alignment,
    score_campaign_concept,
    score_distribution_plan,
)
from backend.models.campaign import CampaignConcept, Channel, ChannelScore, DistributionPlan
from backend.models.company import CompanyProfile


# ---------------------------------------------------------------------------
# Scorer unit tests
# ---------------------------------------------------------------------------


class TestScoreCampaignConcept:
    """Unit tests for score_campaign_concept."""

    def test_ideal_headline_and_body(self) -> None:
        """Headline 5-15 words, body 50-150 words, high confidence -> high score."""
        c = CampaignConcept(
            headline="AI Prediction Markets Are Changing How B2B Teams Forecast",
            body_copy=" ".join(["word"] * 80),
            visual_direction="Dark gradient",
            confidence_score=0.9,
            channel_recommendation=Channel.LINKEDIN,
            channel_reasoning="B2B audience",
        )
        score = score_campaign_concept(c)
        assert 0.8 <= score <= 1.0

    def test_short_headline_penalized(self) -> None:
        """Very short headline reduces score."""
        c = CampaignConcept(
            headline="AI",
            body_copy=" ".join(["word"] * 80),
            visual_direction="",
            confidence_score=0.9,
            channel_recommendation=Channel.TWITTER,
            channel_reasoning="",
        )
        score = score_campaign_concept(c)
        assert score < 0.7

    def test_short_body_penalized(self) -> None:
        """Body under 20 words reduces score."""
        c = CampaignConcept(
            headline="A Good Headline With Five Words",
            body_copy="Too short.",
            visual_direction="",
            confidence_score=0.9,
            channel_recommendation=Channel.TWITTER,
            channel_reasoning="",
        )
        score = score_campaign_concept(c)
        assert score < 0.7

    def test_returns_float_between_0_and_1(self) -> None:
        """Score is always in [0, 1]."""
        c = CampaignConcept(
            headline="X",
            body_copy="Y",
            visual_direction="",
            confidence_score=0.0,
            channel_recommendation=Channel.TWITTER,
            channel_reasoning="",
        )
        score = score_campaign_concept(c)
        assert 0.0 <= score <= 1.0


class TestScoreBrandAlignment:
    """Unit tests for score_brand_alignment."""

    def test_goal_keywords_in_concept(self) -> None:
        """Concept containing campaign_goals keywords scores higher."""
        company = CompanyProfile(
            name="Acme",
            industry="SaaS",
            campaign_goals="drive signups and reduce churn",
            target_audience="developers",
        )
        concept = CampaignConcept(
            headline="Drive signups with prediction markets",
            body_copy="Reduce churn by understanding what developers want.",
            visual_direction="",
            confidence_score=0.8,
            channel_recommendation=Channel.LINKEDIN,
            channel_reasoning="",
        )
        score = score_brand_alignment(concept, company)
        assert score > 0.5

    def test_no_profile_returns_neutral(self) -> None:
        """Company with no goals/audience returns 0.5."""
        company = CompanyProfile(name="X", industry="Y")
        concept = CampaignConcept(
            headline="Anything",
            body_copy="Something",
            visual_direction="",
            confidence_score=0.8,
            channel_recommendation=Channel.TWITTER,
            channel_reasoning="",
        )
        score = score_brand_alignment(concept, company)
        assert score == 0.5


class TestScoreDistributionPlan:
    """Unit tests for score_distribution_plan."""

    def test_with_channel_scores(self) -> None:
        """Plan with good channel scores gets higher score."""
        plan = DistributionPlan(
            campaign_id="c1",
            company_id="co1",
            recommended_channel="linkedin",
            channel_scores=[
                ChannelScore(channel="linkedin", fit_score=0.9, length_fit=0.8, visual_fit=0.9, audience_fit=0.85, reasoning=""),
                ChannelScore(channel="twitter", fit_score=0.6, length_fit=0.5, visual_fit=0.7, audience_fit=0.6, reasoning=""),
            ],
            posting_time="Tuesday 8 AM",
            format_adaptation="Expand for LinkedIn.",
            reasoning="LinkedIn best fits B2B audience.",
            confidence=0.85,
        )
        score = score_distribution_plan(plan)
        assert 0.5 <= score <= 1.0

    def test_empty_channel_scores_uses_confidence(self) -> None:
        """Plan with no channel_scores falls back to confidence."""
        plan = DistributionPlan(
            campaign_id="c1",
            company_id="co1",
            recommended_channel="linkedin",
            channel_scores=[],
            posting_time="Tuesday 8 AM",
            format_adaptation="",
            reasoning="Default fallback.",
            confidence=0.7,
        )
        score = score_distribution_plan(plan)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# TracedRun unit tests (mocked)
# ---------------------------------------------------------------------------


class TestTracedRun:
    """Unit tests for TracedRun context manager."""

    def test_traced_run_yields_helper_when_disabled(self) -> None:
        """When Braintrust is disabled, TracedRun still yields a helper (no-op)."""
        with patch.dict(os.environ, {"BRAINTRUST_API_KEY": ""}, clear=False):
            # Force re-init
            import backend.integrations.braintrust_tracing as bt_module

            bt_module._bt_initialized = False
            bt_module._bt_logger = None

            with TracedRun("test_agent", input={"x": 1}) as span:
                assert span is not None
                span.log_output(output={"y": 2}, scores={"quality": 0.8})
            # No exception

    def test_traced_run_log_output_no_op_when_no_span(self) -> None:
        """log_output on no-op helper does not raise."""
        with patch.dict(os.environ, {"BRAINTRUST_API_KEY": ""}, clear=False):
            import backend.integrations.braintrust_tracing as bt_module

            bt_module._bt_initialized = False
            bt_module._bt_logger = None

            with TracedRun("test_agent", input={}) as span:
                span.log_output(output=None, scores={})
            # No exception


# ---------------------------------------------------------------------------
# get_logger unit tests
# ---------------------------------------------------------------------------


class TestGetLogger:
    """Unit tests for get_logger."""

    def test_returns_none_when_no_api_key(self) -> None:
        """get_logger returns None when BRAINTRUST_API_KEY is not set."""
        with patch.dict(os.environ, {"BRAINTRUST_API_KEY": ""}, clear=False):
            import backend.integrations.braintrust_tracing as bt_module

            bt_module._bt_initialized = False
            bt_module._bt_logger = None

            logger = get_logger()
            assert logger is None

    def test_returns_none_for_placeholder_key(self) -> None:
        """get_logger returns None for placeholder API key."""
        with patch.dict(os.environ, {"BRAINTRUST_API_KEY": "your_braintrust_api_key_here"}, clear=False):
            import backend.integrations.braintrust_tracing as bt_module

            bt_module._bt_initialized = False
            bt_module._bt_logger = None

            logger = get_logger()
            assert logger is None


# ---------------------------------------------------------------------------
# Integration test (live Braintrust)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("BRAINTRUST_API_KEY") or os.getenv("BRAINTRUST_API_KEY") == "your_braintrust_api_key_here",
    reason="BRAINTRUST_API_KEY not set or placeholder",
)
def test_traced_run_live_creates_span() -> None:
    """Create a real trace in Braintrust and assert no exceptions."""
    import backend.integrations.braintrust_tracing as bt_module

    bt_module._bt_initialized = False
    bt_module._bt_logger = None

    with TracedRun("test_integration", input={"test": True, "agent": "braintrust_test"}) as span:
        span.log_output(
            output={"result": "ok"},
            scores={"quality": 0.95},
            metadata={"test_run": True},
        )

    # If we get here without exception, the trace was created
    assert True
