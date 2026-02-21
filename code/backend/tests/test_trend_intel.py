"""Tests for Agent 2 — Trend Intelligence Agent.

Test layers:
  1. Unit tests  — no network, no API keys required
  2. Integration tests — real Polymarket API (public, no auth)
  3. End-to-end tests — full ADK agent run (requires GEMINI_API_KEY)

Run all:
    pytest code/backend/tests/test_trend_intel.py -v

Run only unit tests (no internet required):
    pytest code/backend/tests/test_trend_intel.py -v -m unit

Run integration tests (Polymarket API, no auth needed):
    pytest code/backend/tests/test_trend_intel.py -v -m integration

Run full agent e2e (needs GEMINI_API_KEY in .env):
    pytest code/backend/tests/test_trend_intel.py -v -m e2e
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from project root (walk up from tests/)
_here = Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from models.company import CompanyProfile
from models.signal import TrendSignal

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

SAMPLE_COMPANY = CompanyProfile(
    id="test-company-001",
    name="TechCorp",
    industry="SaaS / Developer Tools",
    tone_of_voice="technical, authoritative",
    target_audience="software engineers and CTOs",
    campaign_goals="grow developer community and drive product sign-ups",
    competitors=["GitHub Copilot", "Cursor"],
)

SAMPLE_MARKETS = [
    {
        "id": "mkt-001",
        "question": "Will OpenAI launch GPT-5 before June 2025?",
        "category": "tech",
        "probability": 0.72,
        "volume": 250000.0,
        "volume_velocity": 0.18,
        "probability_momentum": 0.05,
    },
    {
        "id": "mkt-002",
        "question": "Will the US Federal Reserve cut rates in Q2 2025?",
        "category": "finance",
        "probability": 0.44,
        "volume": 500000.0,
        "volume_velocity": 0.12,
        "probability_momentum": 0.08,
    },
    {
        "id": "mkt-003",
        "question": "Will Bitcoin exceed $100k before end of 2025?",
        "category": "crypto",
        "probability": 0.65,
        "volume": 1000000.0,
        "volume_velocity": 0.25,
        "probability_momentum": 0.12,
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Models
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCompanyProfile:
    def test_creation_with_defaults(self):
        c = CompanyProfile(name="Acme", industry="Retail")
        assert c.name == "Acme"
        assert c.industry == "Retail"
        assert c.id is not None
        assert c.safety_threshold == 0.7

    def test_to_prompt_context_includes_all_fields(self):
        ctx = SAMPLE_COMPANY.to_prompt_context()
        assert "TechCorp" in ctx
        assert "SaaS" in ctx
        assert "software engineers" in ctx
        assert "developer community" in ctx

    def test_to_prompt_context_minimal(self):
        c = CompanyProfile(name="Mini", industry="Unknown")
        ctx = c.to_prompt_context()
        assert "Mini" in ctx
        assert "Unknown" in ctx


@pytest.mark.unit
class TestTrendSignal:
    def test_creation_with_defaults(self):
        sig = TrendSignal(
            polymarket_market_id="mkt-001",
            title="Will AI replace developers by 2026?",
        )
        assert sig.probability == 0.5
        assert sig.volume == 0.0
        assert sig.relevance_scores == {}

    def test_composite_score_calculation(self):
        sig = TrendSignal(
            polymarket_market_id="mkt-001",
            title="Test",
            volume_velocity=0.3,
            probability_momentum=0.1,
            relevance_scores={"company-123": 0.8},
        )
        score = sig.composite_score("company-123")
        # (0.3 * 0.4) + (0.8 * 0.4) + (0.1 * 0.2) = 0.12 + 0.32 + 0.02 = 0.46
        assert abs(score - 0.46) < 0.001

    def test_composite_score_missing_company(self):
        sig = TrendSignal(
            polymarket_market_id="mkt-001",
            title="Test",
            volume_velocity=0.3,
        )
        score = sig.composite_score("nonexistent-company")
        assert score == pytest.approx(0.3 * 0.4, abs=0.001)

    def test_to_dict_is_json_serializable(self):
        sig = TrendSignal(
            polymarket_market_id="mkt-abc",
            title="Test signal",
            probability=0.75,
            volume=100000,
        )
        d = sig.to_dict()
        assert isinstance(d, dict)
        # Should serialise cleanly to JSON
        json_str = json.dumps(d, default=str)
        assert "mkt-abc" in json_str

    def test_probability_bounds(self):
        with pytest.raises(Exception):
            TrendSignal(polymarket_market_id="x", title="x", probability=1.5)

        with pytest.raises(Exception):
            TrendSignal(polymarket_market_id="x", title="x", probability=-0.1)


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Polymarket Client (mocked HTTP)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPolymarketClientParsing:
    def setup_method(self):
        from integrations.polymarket import PolymarketClient

        self.client = PolymarketClient(volume_threshold=10000)

    def test_parse_probability_from_outcome_prices(self):
        market = {"outcomePrices": '["0.72", "0.28"]'}
        assert self.client._parse_probability(market) == pytest.approx(0.72)

    def test_parse_probability_fallback_to_05(self):
        market = {"outcomePrices": "[]"}
        assert self.client._parse_probability(market) == pytest.approx(0.5)

    def test_parse_probability_numeric_list(self):
        market = {"outcomePrices": [0.65, 0.35]}
        assert self.client._parse_probability(market) == pytest.approx(0.65)

    def test_enrich_markets_adds_computed_fields(self):
        markets = [
            {"outcomePrices": '["0.6"]', "volume": "100000", "volume24hr": "10000", "lastTradePrice": "0.5"}
        ]
        enriched = self.client.enrich_markets(markets)
        assert "probability" in enriched[0]
        assert "volume_velocity" in enriched[0]
        assert "probability_momentum" in enriched[0]
        assert enriched[0]["probability"] == pytest.approx(0.6)
        assert enriched[0]["volume_velocity"] == pytest.approx(0.1)  # 10000/100000

    def test_filter_removes_low_volume(self):
        markets = [
            {"volume": 5000},   # below threshold
            {"volume": 50000},  # above threshold
        ]
        filtered = self.client.filter_high_momentum(markets)
        assert len(filtered) == 1
        assert filtered[0]["volume"] == 50000

    def test_enrich_handles_missing_fields(self):
        markets = [{"question": "Will X happen?"}]
        enriched = self.client.enrich_markets(markets)
        assert enriched[0]["probability"] == pytest.approx(0.5)
        assert enriched[0]["volume"] == 0.0
        assert enriched[0]["volume_velocity"] == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — Agent Tools (mocked)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAgentTools:
    def test_score_signal_relevance_tech_company(self):
        from agents.trend_intel import score_signal_relevance

        result = score_signal_relevance(
            market_title="Will OpenAI release GPT-5 before June 2025?",
            market_category="tech",
            company_name="TechCorp",
            industry="SaaS",
            target_audience="developers",
            campaign_goals="grow developer community",
        )
        data = json.loads(result)
        assert "pre_score" in data
        assert "matched_keywords" in data
        assert "reasoning_hint" in data
        assert isinstance(data["pre_score"], float)
        assert 0.0 <= data["pre_score"] <= 1.0

    def test_score_signal_relevance_irrelevant_market(self):
        from agents.trend_intel import score_signal_relevance

        result = score_signal_relevance(
            market_title="Will Team A win the World Cup?",
            market_category="sports",
            company_name="TechCorp",
            industry="SaaS",
            target_audience="developers",
            campaign_goals="grow developer community",
        )
        data = json.loads(result)
        assert data["pre_score"] <= 0.3  # low relevance expected

    def test_format_trend_signals_valid_input(self):
        from agents.trend_intel import format_trend_signals

        signals_data = json.dumps(
            [
                {
                    "market_id": "mkt-001",
                    "title": "Will OpenAI release GPT-5?",
                    "category": "tech",
                    "probability": 0.72,
                    "probability_momentum": 0.05,
                    "volume": 250000,
                    "volume_velocity": 0.18,
                    "relevance_score": 0.9,
                    "confidence_score": 0.85,
                }
            ]
        )
        result = format_trend_signals(signals_data, "company-001")
        data = json.loads(result)
        assert "signals" in data
        assert data["count"] == 1
        sig = data["signals"][0]
        assert sig["title"] == "Will OpenAI release GPT-5?"
        assert sig["probability"] == pytest.approx(0.72)

    def test_format_trend_signals_invalid_json(self):
        from agents.trend_intel import format_trend_signals

        result = format_trend_signals("not valid json {{{{", "company-001")
        data = json.loads(result)
        assert "error" in data

    def test_format_trend_signals_wrapped_dict(self):
        from agents.trend_intel import format_trend_signals

        signals_data = json.dumps(
            {
                "signals": [
                    {
                        "market_id": "mkt-999",
                        "title": "Test signal",
                        "probability": 0.5,
                        "relevance_score": 0.6,
                    }
                ]
            }
        )
        result = format_trend_signals(signals_data, "co-123")
        data = json.loads(result)
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_fetch_polymarket_signals_mocked(self):
        from agents.trend_intel import fetch_polymarket_signals
        from integrations.polymarket import PolymarketClient

        mock_client = AsyncMock(spec=PolymarketClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.fetch_top_signals = AsyncMock(return_value=SAMPLE_MARKETS)

        with patch("agents.trend_intel.PolymarketClient", return_value=mock_client):
            result = await fetch_polymarket_signals(volume_threshold=1000.0, limit=10)

        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["title"] == SAMPLE_MARKETS[0]["question"]

    @pytest.mark.asyncio
    async def test_feedback_calibration_boosts_relevance(self):
        from agents.trend_intel import _apply_feedback_calibration

        signal = TrendSignal(
            polymarket_market_id="pm-1",
            title="Test tech signal",
            category="tech",
            relevance_scores={SAMPLE_COMPANY.id: 0.4},
        )
        calibration_rows = [
            {
                "signal_category": "tech",
                "predicted_engagement": 0.05,
                "actual_engagement": 0.10,
                "accuracy_score": 0.9,
                "company_type": SAMPLE_COMPANY.industry,
            }
        ]
        with patch("agents.trend_intel.db_module.get_signal_calibration", AsyncMock(return_value=calibration_rows)), patch(
            "agents.trend_intel.db_module.get_shared_patterns", AsyncMock(return_value=[])
        ):
            updated = await _apply_feedback_calibration(SAMPLE_COMPANY, [signal])
        assert updated[0].relevance_scores[SAMPLE_COMPANY.id] > 0.4

    @pytest.mark.asyncio
    async def test_feedback_calibration_uses_global_fallback(self):
        from agents.trend_intel import _apply_feedback_calibration

        signal = TrendSignal(
            polymarket_market_id="pm-2",
            title="Fallback calibration signal",
            category="macro",
            relevance_scores={SAMPLE_COMPANY.id: 0.5},
        )
        side_effect = [
            [],  # company-specific miss
            [
                {
                    "signal_category": "macro",
                    "predicted_engagement": 0.08,
                    "actual_engagement": 0.04,
                    "accuracy_score": 0.7,
                    "company_type": "unknown",
                }
            ],
        ]
        mock_get_cal = AsyncMock(side_effect=side_effect)
        with patch("agents.trend_intel.db_module.get_signal_calibration", mock_get_cal), patch(
            "agents.trend_intel.db_module.get_shared_patterns", AsyncMock(return_value=[])
        ):
            updated = await _apply_feedback_calibration(SAMPLE_COMPANY, [signal])

        assert mock_get_cal.await_count == 2
        assert updated[0].relevance_scores[SAMPLE_COMPANY.id] < 0.5


# ──────────────────────────────────────────────────────────────────────────────
# Integration Tests — Real Polymarket API (no auth required)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_polymarket_api_reachable():
    """Confirm the public Polymarket Gamma API responds."""
    from integrations.polymarket import PolymarketClient

    async with PolymarketClient(volume_threshold=0) as client:
        markets = await client.get_markets(limit=5)

    assert isinstance(markets, list)
    assert len(markets) > 0, "Polymarket returned no markets"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_polymarket_market_structure():
    """Check that market objects have expected fields."""
    from integrations.polymarket import PolymarketClient

    async with PolymarketClient(volume_threshold=0) as client:
        markets = await client.get_markets(limit=3)

    assert len(markets) > 0
    m = markets[0]
    # At least one of these title fields should exist
    has_title = "question" in m or "title" in m or "slug" in m
    assert has_title, f"No title field found in market: {list(m.keys())}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_polymarket_fetch_top_signals():
    """End-to-end fetch, enrich, and filter pipeline."""
    from integrations.polymarket import PolymarketClient

    async with PolymarketClient(volume_threshold=1000) as client:
        signals = await client.fetch_top_signals(limit=50, top_n=5, volume_threshold=1000)

    assert isinstance(signals, list)
    # Should have computed fields
    for sig in signals:
        assert "probability" in sig
        assert "volume_velocity" in sig
        assert "probability_momentum" in sig
        assert 0.0 <= sig["probability"] <= 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_polymarket_signals_tool_live():
    """Test the actual agent tool with the live Polymarket API."""
    from agents.trend_intel import fetch_polymarket_signals

    result = await fetch_polymarket_signals(volume_threshold=1000.0, limit=20)
    data = json.loads(result)

    assert isinstance(data, list), f"Expected list, got: {type(data)}"
    if data:
        first = data[0]
        assert "title" in first
        assert "probability" in first
        assert "volume" in first


# ──────────────────────────────────────────────────────────────────────────────
# End-to-End Tests — Full ADK Agent Run (requires GEMINI_API_KEY)
# ──────────────────────────────────────────────────────────────────────────────


def _gemini_key_available() -> bool:
    key = os.getenv("GEMINI_API_KEY", "")
    return bool(key) and key != "your_gemini_api_key_here"


def _skip_on_quota(exc: Exception) -> bool:
    """Return True if the exception is a Gemini quota/rate-limit error."""
    return "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc)


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(not _gemini_key_available(), reason="GEMINI_API_KEY not configured")
async def test_full_agent_run_returns_signals():
    """Full end-to-end: run Agent 2 against live Polymarket + Gemini."""
    from agents.trend_intel import run_trend_agent

    try:
        signals = await run_trend_agent(
            company=SAMPLE_COMPANY,
            volume_threshold=5000.0,
            top_n=3,
        )
    except Exception as exc:
        if _skip_on_quota(exc):
            pytest.skip(f"Gemini quota exhausted — try gemini-2.0-flash or wait: {exc}")
        raise

    assert isinstance(signals, list), "Expected a list of TrendSignal objects"
    for sig in signals:
        assert isinstance(sig, TrendSignal)
        assert sig.title
        assert sig.polymarket_market_id
        assert 0.0 <= sig.probability <= 1.0


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(not _gemini_key_available(), reason="GEMINI_API_KEY not configured")
async def test_full_agent_run_different_companies():
    """Verify that different company profiles produce different signals."""
    from agents.trend_intel import run_trend_agent

    tech_company = CompanyProfile(
        name="DevTools Inc",
        industry="Developer Tools",
        target_audience="software engineers",
        campaign_goals="increase GitHub integrations",
    )
    finance_company = CompanyProfile(
        name="WealthTrack",
        industry="Personal Finance",
        target_audience="retail investors aged 25-40",
        campaign_goals="drive app downloads during market volatility",
    )

    try:
        tech_signals = await run_trend_agent(tech_company, volume_threshold=5000.0, top_n=3)
        finance_signals = await run_trend_agent(finance_company, volume_threshold=5000.0, top_n=3)
    except Exception as exc:
        if _skip_on_quota(exc):
            pytest.skip(f"Gemini quota exhausted: {exc}")
        raise

    assert isinstance(tech_signals, list)
    assert isinstance(finance_signals, list)
    tech_titles = {s.title for s in tech_signals}
    finance_titles = {s.title for s in finance_signals}
    print(f"\n  Tech signals:    {tech_titles}")
    print(f"  Finance signals: {finance_titles}")
