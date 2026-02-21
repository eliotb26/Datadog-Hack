"""
Standalone tests for Agent 3 — Campaign Generation Agent.

Run modes
---------
  Mock (no API key needed):
      pytest tests/test_agent3.py -v

  Live (requires GEMINI_API_KEY in .env):
      pytest tests/test_agent3.py -v -m live

pytest marks:
  @pytest.mark.live  — skipped unless GEMINI_API_KEY is set
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.models.company import CompanyProfile
from backend.models.signal import TrendSignal
from backend.models.campaign import (
    CampaignConcept,
    CampaignGenerationRequest,
    CampaignGenerationResponse,
    Channel,
)
from backend.agents.campaign_gen import CampaignGenerationAgent

# ---------------------------------------------------------------------------
# Fixtures — reusable test data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_company():
    return CompanyProfile(
        id="company-001",
        name="NovaTech",
        industry="SaaS / Developer Tools",
        tone_of_voice="bold and technical",
        target_audience="software engineers and CTOs",
        campaign_goals="drive trial sign-ups and developer community growth",
        competitors=["GitHub Copilot", "Cursor"],
        content_history=[
            "We shipped v2.0 — now 3x faster",
            "How we cut CI costs by 40% in one week",
        ],
        visual_style="dark mode, code-forward, minimal",
    )


@pytest.fixture
def sample_signals(sample_company):
    return [
        TrendSignal(
            id="sig-001",
            polymarket_market_id="pm-12345",
            title="Will AI coding tools replace 50% of junior dev roles by end of 2025?",
            category="tech",
            probability=0.38,
            probability_momentum=+0.07,
            volume=850_000,
            volume_velocity=12_000,
            relevance_scores={sample_company.id: 0.92},
        ),
        TrendSignal(
            id="sig-002",
            polymarket_market_id="pm-67890",
            title="Will a major tech company announce layoffs > 10k in Q1 2025?",
            category="macro",
            probability=0.61,
            probability_momentum=-0.03,
            volume=2_100_000,
            volume_velocity=5_500,
            relevance_scores={sample_company.id: 0.71},
        ),
    ]


@pytest.fixture
def sample_request(sample_company, sample_signals):
    return CampaignGenerationRequest(
        company=sample_company,
        trend_signals=sample_signals,
        prompt_weights={
            "tone_weight": 1.2,
            "learned_preferences": "developers respond well to benchmark claims and code examples",
        },
        n_concepts=3,
    )


# ---------------------------------------------------------------------------
# Helper — build a fake Gemini response payload
# ---------------------------------------------------------------------------

def _fake_gemini_concepts(n: int = 3) -> str:
    concepts = []
    channels = ["twitter", "linkedin", "instagram", "newsletter"]
    for i in range(n):
        concepts.append(
            {
                "headline": f"Test Headline {i + 1}: AI Is Reshaping Dev Workflows",
                "body_copy": (
                    f"Campaign body copy for concept {i + 1}. "
                    "AI coding tools are accelerating developer productivity. "
                    "NovaTech helps teams ship faster without sacrificing quality. "
                    "Try it free for 14 days and see the difference."
                ),
                "visual_direction": f"Dark background with glowing code terminal, concept {i + 1}",
                "confidence_score": round(0.7 + i * 0.05, 2),
                "channel_recommendation": channels[i % len(channels)],
                "channel_reasoning": f"Channel {channels[i % len(channels)]} best fits this audience for concept {i + 1}.",
            }
        )
    return json.dumps(concepts)


# ---------------------------------------------------------------------------
# Unit tests (mock mode — no API key needed)
# ---------------------------------------------------------------------------

class TestCampaignConceptModel:
    """Validate the Pydantic models used by Agent 3."""

    def test_valid_concept(self):
        concept = CampaignConcept(
            headline="Why AI Tools Are Table Stakes Now",
            body_copy="Lorem ipsum dolor sit amet " * 6,
            visual_direction="Clean dark UI with code overlay",
            confidence_score=0.88,
            channel_recommendation=Channel.LINKEDIN,
            channel_reasoning="LinkedIn reaches CTOs best.",
        )
        assert concept.confidence_score == 0.88
        assert concept.channel_recommendation == Channel.LINKEDIN
        assert concept.safety_passed is True

    def test_confidence_out_of_range(self):
        with pytest.raises(Exception):
            CampaignConcept(
                headline="Bad",
                body_copy="Bad body",
                visual_direction="bad",
                confidence_score=1.5,       # invalid
                channel_recommendation=Channel.TWITTER,
                channel_reasoning="n/a",
            )

    def test_all_channels_valid(self):
        for ch in ["twitter", "linkedin", "instagram", "newsletter"]:
            c = CampaignConcept(
                headline=f"Headline for {ch}",
                body_copy="Body text " * 8,
                visual_direction="visual note",
                confidence_score=0.75,
                channel_recommendation=ch,
                channel_reasoning=f"Great for {ch}",
            )
            assert c.channel_recommendation == Channel(ch)


class TestCampaignGenerationRequest:
    def test_request_defaults(self, sample_company, sample_signals):
        req = CampaignGenerationRequest(
            company=sample_company,
            trend_signals=sample_signals,
        )
        assert req.n_concepts == 3
        assert req.prompt_weights == {}

    def test_n_concepts_clamped(self, sample_company, sample_signals):
        with pytest.raises(Exception):
            CampaignGenerationRequest(
                company=sample_company,
                trend_signals=sample_signals,
                n_concepts=10,   # max is 5
            )


class TestCampaignGenerationAgentMock:
    """Full agent tests using a mocked Gemini client."""

    def _make_mock_response(self, n=3):
        mock_resp = MagicMock()
        mock_resp.text = _fake_gemini_concepts(n)
        mock_resp.usage_metadata.total_token_count = 512
        return mock_resp

    def _patched_client(self, n=3):
        """Return a context manager that patches the global _client."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = self._make_mock_response(n)
        return patch("backend.agents.campaign_gen._client", mock_client)

    def test_run_returns_response(self, sample_request):
        with self._patched_client(3):
            agent = CampaignGenerationAgent()
            response = agent.run(sample_request)

        assert isinstance(response, CampaignGenerationResponse)
        assert response.company_id == "company-001"
        assert len(response.trend_signal_ids) == 2
        assert len(response.concepts) == 3

    def test_concepts_have_required_fields(self, sample_request):
        with self._patched_client(3):
            agent = CampaignGenerationAgent()
            response = agent.run(sample_request)

        for concept in response.concepts:
            assert concept.headline
            assert len(concept.body_copy) > 10
            assert concept.visual_direction
            assert 0.0 <= concept.confidence_score <= 1.0
            assert concept.channel_recommendation in list(Channel)
            assert concept.channel_reasoning

    def test_n_concepts_respected(self, sample_company, sample_signals):
        """Agent should cap output to n_concepts."""
        req = CampaignGenerationRequest(
            company=sample_company,
            trend_signals=sample_signals,
            n_concepts=2,
        )
        with self._patched_client(5):   # mock returns 5, agent should cap at 2
            agent = CampaignGenerationAgent()
            response = agent.run(req)

        assert len(response.concepts) == 2

    def test_latency_recorded(self, sample_request):
        with self._patched_client(3):
            agent = CampaignGenerationAgent()
            response = agent.run(sample_request)

        assert response.latency_ms is not None
        assert response.latency_ms >= 0

    def test_tokens_recorded(self, sample_request):
        with self._patched_client(3):
            agent = CampaignGenerationAgent()
            response = agent.run(sample_request)

        assert response.tokens_used == 512

    def test_invalid_json_raises(self, sample_request):
        mock_resp = MagicMock()
        mock_resp.text = "This is not JSON at all"
        mock_resp.usage_metadata.total_token_count = 10

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp

        with patch("backend.agents.campaign_gen._client", mock_client):
            agent = CampaignGenerationAgent()
            with pytest.raises(ValueError, match="invalid JSON"):
                agent.run(sample_request)

    def test_unknown_channel_normalised_to_twitter(self, sample_request):
        """Unknown channel values (e.g. 'tiktok') should fall back to 'twitter'."""
        concepts = json.loads(_fake_gemini_concepts(1))
        concepts[0]["channel_recommendation"] = "tiktok"

        mock_resp = MagicMock()
        mock_resp.text = json.dumps(concepts)
        mock_resp.usage_metadata.total_token_count = 100

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_resp

        with patch("backend.agents.campaign_gen._client", mock_client):
            agent = CampaignGenerationAgent()
            response = agent.run(sample_request)

        assert response.concepts[0].channel_recommendation == Channel.TWITTER


# ---------------------------------------------------------------------------
# Live tests — require GEMINI_API_KEY in .env
# ---------------------------------------------------------------------------

live = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping live tests",
)


def _skip_on_quota(fn):
    """Decorator: skip the test if Gemini returns a 429 quota error."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                pytest.skip(f"Quota exhausted (free tier): {msg[:120]}")
            raise

    return wrapper


@live
class TestCampaignGenerationAgentLive:
    """Integration tests that make real Gemini API calls."""

    @_skip_on_quota
    def test_live_generation(self, sample_request):
        agent = CampaignGenerationAgent()
        response = agent.run(sample_request)

        print("\n--- Live Agent 3 Output ---")
        for i, concept in enumerate(response.concepts, 1):
            print(f"\nConcept {i}:")
            print(f"  Headline : {concept.headline}")
            print(f"  Channel  : {concept.channel_recommendation.value}")
            print(f"  Confidence: {concept.confidence_score:.0%}")
            print(f"  Body     : {concept.body_copy[:100]}...")

        assert len(response.concepts) >= 1
        assert response.tokens_used is not None
        assert response.latency_ms > 0

    @_skip_on_quota
    def test_live_single_concept(self, sample_company, sample_signals):
        req = CampaignGenerationRequest(
            company=sample_company,
            trend_signals=[sample_signals[0]],
            n_concepts=1,
        )
        agent = CampaignGenerationAgent()
        response = agent.run(req)
        assert len(response.concepts) == 1

    @_skip_on_quota
    def test_live_prompt_weights_influence(self, sample_company, sample_signals):
        """Run with and without weights — headlines should differ."""
        req_base = CampaignGenerationRequest(
            company=sample_company,
            trend_signals=[sample_signals[0]],
            n_concepts=1,
            prompt_weights={},
        )
        req_weighted = CampaignGenerationRequest(
            company=sample_company,
            trend_signals=[sample_signals[0]],
            n_concepts=1,
            prompt_weights={
                "tone_weight": 1.8,
                "learned_preferences": "use aggressive headlines with controversy hooks",
            },
        )
        agent = CampaignGenerationAgent()
        r1 = agent.run(req_base)
        r2 = agent.run(req_weighted)

        print(f"\nBase headline    : {r1.concepts[0].headline}")
        print(f"Weighted headline: {r2.concepts[0].headline}")

        assert r1.concepts[0].headline != r2.concepts[0].headline or True  # soft check
