"""
Tests for Agent 3 — Campaign Generation Agent

Test layers:
  1. Unit tests     — no API key required (models + tools in isolation)
  2. Integration    — DB persistence with a real temp SQLite file
  3. End-to-end     — full ADK agent run (requires GEMINI_API_KEY)

Run all unit tests (no API key needed):
    cd code
    pytest tests/test_agent3_campaign_gen.py -v -m unit

Run integration tests (no API key needed):
    pytest tests/test_agent3_campaign_gen.py -v -m integration

Run e2e (requires GEMINI_API_KEY in .env):
    pytest tests/test_agent3_campaign_gen.py -v -m e2e
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv

# Make backend importable from code/ (for backend.xxx imports)
# and code/backend/ (for bare imports used inside campaign_gen.py tools)
_code_dir = Path(__file__).parent.parent
_backend_dir = _code_dir / "backend"
sys.path.insert(0, str(_code_dir))
sys.path.insert(0, str(_backend_dir))

# Load .env from the repo root
_here = Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from backend.models.company import CompanyProfile
from backend.models.signal import TrendSignal
from backend.models.campaign import (
    CampaignConcept,
    CampaignGenerationResponse,
    Channel,
)
from backend.agents.campaign_gen import (
    validate_campaign_concept,
    format_campaign_concepts,
    _build_user_prompt,
    _build_instruction,
    _extract_concepts_from_response,
    _persist_agent_traces,
)
from backend.routers.campaigns import _load_feedback_prompt_weights
from backend.config import settings


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_company() -> CompanyProfile:
    return CompanyProfile(
        id="company-001",
        name="NovaTech",
        industry="SaaS / Developer Tools",
        tone_of_voice="bold, technical, slightly witty",
        target_audience="software engineers and CTOs",
        campaign_goals="drive trial sign-ups and developer community growth",
        competitors=["GitHub Copilot", "Cursor"],
        content_history=[
            "We shipped v2.0 — now 3× faster",
            "How we cut CI costs by 40% in one week",
        ],
        visual_style="dark mode, code-forward, minimal",
    )


@pytest.fixture
def sample_signals(sample_company) -> list:
    return [
        TrendSignal(
            id="sig-001",
            polymarket_market_id="pm-12345",
            title="Will AI coding tools replace 50% of junior dev roles by end of 2025?",
            category="tech",
            probability=0.38,
            probability_momentum=0.07,
            volume=850_000,
            volume_velocity=0.18,
            relevance_scores={sample_company.id: 0.92},
            confidence_score=0.85,
        ),
        TrendSignal(
            id="sig-002",
            polymarket_market_id="pm-67890",
            title="Will a major tech company announce layoffs > 10k in Q1 2025?",
            category="macro",
            probability=0.61,
            probability_momentum=-0.03,
            volume=2_100_000,
            volume_velocity=0.12,
            relevance_scores={sample_company.id: 0.71},
            confidence_score=0.78,
        ),
    ]


def _make_concepts_json(n: int = 3) -> str:
    """Build a fake LLM output with n campaign concepts."""
    channels = ["twitter", "linkedin", "instagram", "newsletter"]
    concepts = [
        {
            "headline": f"Concept {i + 1}: AI Is Reshaping Developer Workflows",
            "body_copy": (
                f"Campaign body for concept {i + 1}. "
                "AI coding tools are transforming how developers work. "
                "NovaTech helps teams ship faster without sacrificing quality. "
                "Start your free 14-day trial today and see the difference."
            ),
            "visual_direction": f"Dark terminal background, glowing code — concept {i + 1}",
            "confidence_score": round(0.70 + i * 0.05, 2),
            "channel_recommendation": channels[i % len(channels)],
            "channel_reasoning": f"Best reach for target audience on {channels[i % len(channels)]}.",
        }
        for i in range(n)
    ]
    return json.dumps(concepts)


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — CampaignConcept model
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCampaignConceptModel:
    def test_valid_concept_creation(self):
        c = CampaignConcept(
            headline="Why AI Tools Are Table Stakes Now",
            body_copy="Body copy here " * 6,
            visual_direction="Dark UI with code overlay",
            confidence_score=0.88,
            channel_recommendation=Channel.LINKEDIN,
            channel_reasoning="LinkedIn reaches CTOs best.",
        )
        assert c.confidence_score == 0.88
        assert c.channel_recommendation == Channel.LINKEDIN
        assert c.safety_passed is True
        assert c.status == "draft"
        assert c.id  # UUID assigned automatically

    def test_confidence_score_out_of_range(self):
        with pytest.raises(Exception):
            CampaignConcept(
                headline="Bad",
                body_copy="Bad body " * 8,
                visual_direction="visual",
                confidence_score=1.5,
                channel_recommendation=Channel.TWITTER,
                channel_reasoning="n/a",
            )

    def test_all_channels_accepted(self):
        for ch in ["twitter", "linkedin", "instagram", "newsletter"]:
            c = CampaignConcept(
                headline=f"Headline for {ch}",
                body_copy="Body text " * 8,
                visual_direction="visual",
                confidence_score=0.75,
                channel_recommendation=ch,
                channel_reasoning=f"Great for {ch}",
            )
            assert c.channel_recommendation == Channel(ch)

    def test_to_db_row_serialises_channel_as_string(self):
        c = CampaignConcept(
            headline="Test",
            body_copy="Test body " * 7,
            visual_direction="v",
            confidence_score=0.8,
            channel_recommendation=Channel.INSTAGRAM,
            channel_reasoning="visual platform",
        )
        row = c.to_db_row()
        assert row["channel_recommendation"] == "instagram"
        assert isinstance(row["created_at"], str)

    def test_from_db_row_round_trip(self):
        original = CampaignConcept(
            id="abc-123",
            company_id="co-001",
            headline="Round Trip Test",
            body_copy="Round trip body copy " * 5,
            visual_direction="minimal",
            confidence_score=0.82,
            channel_recommendation=Channel.NEWSLETTER,
            channel_reasoning="email list is warm",
        )
        row = original.to_db_row()
        restored = CampaignConcept.from_db_row(row)
        assert restored.id == original.id
        assert restored.headline == original.headline
        assert restored.channel_recommendation == Channel.NEWSLETTER
        assert abs(restored.confidence_score - 0.82) < 0.001


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — validate_campaign_concept tool
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidateCampaignConcept:
    def test_valid_concept_passes(self):
        result = json.loads(validate_campaign_concept(
            headline="Bold AI Headline Here",
            body_copy=(
                "This campaign body copy has well over twenty words so it passes the minimum "
                "word count validation check that the tool enforces on every concept."
            ),
            channel_recommendation="linkedin",
            confidence_score=0.85,
        ))
        assert result["is_valid"] is True
        assert result["issues"] == []
        assert result["adjusted_confidence"] == pytest.approx(0.85)

    def test_empty_headline_fails(self):
        result = json.loads(validate_campaign_concept(
            headline="",
            body_copy="This body copy is long enough to pass the word count check easily.",
            channel_recommendation="twitter",
            confidence_score=0.8,
        ))
        assert result["is_valid"] is False
        assert any("headline" in issue for issue in result["issues"])

    def test_short_body_copy_fails(self):
        result = json.loads(validate_campaign_concept(
            headline="Valid Headline",
            body_copy="Too short.",
            channel_recommendation="twitter",
            confidence_score=0.8,
        ))
        assert result["is_valid"] is False
        assert any("body_copy" in issue for issue in result["issues"])

    def test_invalid_channel_fails(self):
        result = json.loads(validate_campaign_concept(
            headline="Valid Headline",
            body_copy="Body copy that is long enough to pass the minimum word count validation check.",
            channel_recommendation="tiktok",
            confidence_score=0.8,
        ))
        assert result["is_valid"] is False
        assert any("tiktok" in issue for issue in result["issues"])

    def test_confidence_out_of_range_fails(self):
        result = json.loads(validate_campaign_concept(
            headline="Headline",
            body_copy="Body copy that is long enough to pass the minimum word count check here.",
            channel_recommendation="twitter",
            confidence_score=1.5,
        ))
        assert result["is_valid"] is False

    def test_adjusted_confidence_penalised(self):
        result = json.loads(validate_campaign_concept(
            headline="",          # 1 issue
            body_copy="Short.",   # another issue
            channel_recommendation="twitter",
            confidence_score=0.9,
        ))
        assert result["adjusted_confidence"] < 0.9


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — format_campaign_concepts tool
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestFormatCampaignConcepts:
    def test_valid_concepts_normalised(self):
        raw = _make_concepts_json(3)
        result = json.loads(format_campaign_concepts(raw, "co-001", "sig-001"))
        assert result["count"] == 3
        assert result["company_id"] == "co-001"
        for concept in result["concepts"]:
            assert concept["headline"]
            assert concept["body_copy"]
            assert concept["channel_recommendation"] in {"twitter", "linkedin", "instagram", "newsletter"}

    def test_invalid_json_returns_error(self):
        result = json.loads(format_campaign_concepts("NOT JSON {{{{", "co-001", "sig-001"))
        assert "error" in result
        assert result["count"] == 0

    def test_unknown_channel_normalised_to_twitter(self):
        concepts = json.loads(_make_concepts_json(1))
        concepts[0]["channel_recommendation"] = "tiktok"
        result = json.loads(format_campaign_concepts(json.dumps(concepts), "co-001", "sig-001"))
        assert result["concepts"][0]["channel_recommendation"] == "twitter"

    def test_wrapped_dict_format_accepted(self):
        payload = json.dumps({"concepts": json.loads(_make_concepts_json(2))})
        result = json.loads(format_campaign_concepts(payload, "co-001", "sig-001"))
        assert result["count"] == 2

    def test_company_id_attached_to_concepts(self):
        raw = _make_concepts_json(2)
        result = json.loads(format_campaign_concepts(raw, "co-xyz", "sig-abc"))
        for concept in result["concepts"]:
            assert concept["company_id"] == "co-xyz"
            assert concept["trend_signal_id"] == "sig-abc"


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — prompt builders
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestPromptBuilders:
    def test_user_prompt_contains_signal_titles(self, sample_company, sample_signals):
        prompt = _build_user_prompt(sample_company, sample_signals, 3)
        assert "AI coding tools" in prompt
        assert "layoffs" in prompt
        assert "NovaTech" in prompt

    def test_instruction_contains_company_info(self, sample_company):
        instruction = _build_instruction(sample_company, {}, 3)
        assert "NovaTech" in instruction
        assert "SaaS" in instruction
        assert "software engineers" in instruction
        assert "twitter/linkedin/instagram/newsletter" in instruction

    def test_instruction_includes_tone_weight(self, sample_company):
        instruction = _build_instruction(
            sample_company,
            {"tone_weight": 1.8, "learned_preferences": "use aggressive hooks"},
            3,
        )
        assert "1.80" in instruction
        assert "aggressive hooks" in instruction

    def test_instruction_n_concepts(self, sample_company):
        instruction = _build_instruction(sample_company, {}, 5)
        assert "5" in instruction


@pytest.mark.unit
@pytest.mark.asyncio
async def test_feedback_weights_include_shared_patterns(sample_company):
    with patch("backend.routers.campaigns.db_module.get_prompt_weights", AsyncMock(return_value={"tone_weight": 1.4})), patch(
        "backend.routers.campaigns.db_module.get_shared_patterns",
        AsyncMock(
            return_value=[
                {
                    "description": "In SaaS, linkedin performs best for technical buyers.",
                    "effect": {"recommended_channel": "linkedin"},
                }
            ]
        ),
    ):
        merged = await _load_feedback_prompt_weights(sample_company)

    assert merged["tone_weight"] == pytest.approx(1.4)
    assert "learned_preferences" in merged
    assert "linkedin" in merged["learned_preferences"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — response extraction
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestExtractConceptsFromResponse:
    def test_extracts_from_json_code_block(self, sample_company, sample_signals):
        raw = _make_concepts_json(2)
        text = f"Here are the campaigns:\n```json\n{raw}\n```"
        result = _extract_concepts_from_response(text, sample_company.id, sample_signals)
        assert len(result) == 2
        assert all(isinstance(c, CampaignConcept) for c in result)

    def test_extracts_from_format_tool_wrapper(self, sample_company, sample_signals):
        concepts_list = json.loads(_make_concepts_json(3))
        payload = json.dumps({"concepts": concepts_list, "count": 3, "company_id": sample_company.id})
        text = f"Done! ```json\n{payload}\n```"
        result = _extract_concepts_from_response(text, sample_company.id, sample_signals)
        assert len(result) == 3

    def test_returns_empty_on_no_json(self, sample_company, sample_signals):
        result = _extract_concepts_from_response(
            "I generated some campaigns but didn't format them.", sample_company.id, sample_signals
        )
        assert result == []

    def test_unknown_channel_normalised(self, sample_company, sample_signals):
        concepts = json.loads(_make_concepts_json(1))
        concepts[0]["channel_recommendation"] = "snapchat"
        text = f"```json\n{json.dumps(concepts)}\n```"
        result = _extract_concepts_from_response(text, sample_company.id, sample_signals)
        assert result[0].channel_recommendation == Channel.TWITTER


# ──────────────────────────────────────────────────────────────────────────────
# Integration Tests — DB persistence
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_persist_campaigns_writes_to_db(sample_company, sample_signals, tmp_path):
    """Confirm _persist_campaigns saves concepts to the campaigns SQLite table."""
    import aiosqlite
    import backend.database as db_module

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    from backend.agents.campaign_gen import _persist_campaigns
    from backend.database import init_db

    try:
        await init_db(test_db)

        concepts = [
            CampaignConcept(
                company_id=sample_company.id,
                trend_signal_id=sample_signals[0].id,
                headline=f"Test Headline {i + 1}",
                body_copy="Test body copy with enough words to make it valid and realistic enough.",
                visual_direction="dark background, code terminal",
                confidence_score=0.80 + i * 0.05,
                channel_recommendation=Channel.LINKEDIN,
                channel_reasoning="LinkedIn best for B2B reach.",
            )
            for i in range(3)
        ]

        await _persist_campaigns(concepts)

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM campaigns")
            count = (await cursor.fetchone())[0]
            assert count == 3

            cursor = await db.execute("SELECT headline FROM campaigns ORDER BY headline")
            rows = await cursor.fetchall()
            headlines = [row[0] for row in rows]
            assert "Test Headline 1" in headlines

    finally:
        db_module.DB_PATH = original


@pytest.mark.integration
@pytest.mark.asyncio
async def test_persist_agent_traces_writes_rows(sample_company, sample_signals, tmp_path):
    """Confirm campaign agent trace rows are persisted alongside generated concepts."""
    import aiosqlite
    import backend.database as db_module
    from backend.database import init_db

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    try:
        await init_db(test_db)
        concepts = [
            CampaignConcept(
                id=f"camp-{i}",
                company_id=sample_company.id,
                trend_signal_id=sample_signals[0].id,
                headline=f"Trace headline {i}",
                body_copy="Trace test body copy with enough words for validation and scoring.",
                visual_direction="minimal",
                confidence_score=0.8,
                channel_recommendation=Channel.LINKEDIN,
                channel_reasoning="B2B audience fit.",
            )
            for i in range(2)
        ]

        await _persist_agent_traces(
            concepts=concepts,
            company=sample_company,
            signals=sample_signals,
            latency_ms=1234,
            braintrust_trace_id="trace-123",
        )

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT agent_name, company_id, output_summary, braintrust_trace_id, latency_ms "
                "FROM agent_traces ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()

        assert len(rows) == 2
        assert all(r[0] == "campaign_gen" for r in rows)
        assert all(r[1] == sample_company.id for r in rows)
        assert all("campaign_id=camp-" in r[2] for r in rows)
        assert all(r[3] == "trace-123" for r in rows)
        assert all(r[4] == 1234 for r in rows)

    finally:
        db_module.DB_PATH = original


@pytest.mark.integration
@pytest.mark.asyncio
async def test_campaign_db_row_round_trip(tmp_path):
    """Verify to_db_row + from_db_row recovers original data faithfully."""
    import aiosqlite
    import backend.database as db_module
    from backend.database import init_db
    from backend.agents.campaign_gen import _persist_campaigns

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    try:
        await init_db(test_db)
        concept = CampaignConcept(
            id="round-trip-id",
            company_id="co-001",
            trend_signal_id="sig-001",
            headline="Round Trip Test Headline",
            body_copy="Round trip body copy with enough words to be valid and pass basic checks.",
            visual_direction="minimal dark UI",
            confidence_score=0.77,
            channel_recommendation=Channel.NEWSLETTER,
            channel_reasoning="Newsletter audience is warm and engaged.",
        )
        await _persist_campaigns([concept])

        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM campaigns WHERE id = ?", ("round-trip-id",))
            row = dict(await cursor.fetchone())

        restored = CampaignConcept.from_db_row(row)
        assert restored.id == "round-trip-id"
        assert restored.headline == "Round Trip Test Headline"
        assert restored.channel_recommendation == Channel.NEWSLETTER
        assert abs(restored.confidence_score - 0.77) < 0.001

    finally:
        db_module.DB_PATH = original


# ──────────────────────────────────────────────────────────────────────────────
# End-to-End Tests — Full ADK Agent Run (requires GEMINI_API_KEY)
# ──────────────────────────────────────────────────────────────────────────────

def _gemini_key_available() -> bool:
    key = os.getenv("GEMINI_API_KEY", "")
    return bool(key) and key != "your_gemini_api_key_here"


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(not _gemini_key_available(), reason="GEMINI_API_KEY not configured")
async def test_full_agent_run_returns_concepts(sample_company, sample_signals, tmp_path):
    """Full end-to-end: Agent 3 generates concepts via Gemini + ADK."""
    import backend.database as db_module
    from backend.agents.campaign_gen import run_campaign_agent

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    try:
        response = await run_campaign_agent(
            company=sample_company,
            signals=sample_signals,
            n_concepts=3,
            persist=True,
        )

        assert isinstance(response, CampaignGenerationResponse)
        assert response.success
        assert len(response.concepts) >= 1
        assert response.latency_ms > 0

        for c in response.concepts:
            assert isinstance(c, CampaignConcept)
            assert c.headline
            assert c.body_copy
            assert c.channel_recommendation in list(Channel)
            assert 0.0 <= c.confidence_score <= 1.0

        print(f"\n--- Agent 3 Live Output ({len(response.concepts)} concepts) ---")
        for i, c in enumerate(response.concepts, 1):
            print(f"\nConcept {i}: {c.headline}")
            print(f"  Channel    : {c.channel_recommendation.value}")
            print(f"  Confidence : {c.confidence_score:.0%}")
            print(f"  Body       : {c.body_copy[:120]}...")

    finally:
        db_module.DB_PATH = original


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(not _gemini_key_available(), reason="GEMINI_API_KEY not configured")
async def test_prompt_weights_applied(sample_company, sample_signals, tmp_path):
    """Concepts with a high tone_weight should feel tonally different from neutral."""
    import backend.database as db_module
    from backend.agents.campaign_gen import run_campaign_agent

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    try:
        r_neutral = await run_campaign_agent(
            company=sample_company,
            signals=[sample_signals[0]],
            prompt_weights={},
            n_concepts=1,
            persist=False,
        )
        r_aggressive = await run_campaign_agent(
            company=sample_company,
            signals=[sample_signals[0]],
            prompt_weights={
                "tone_weight": 2.0,
                "learned_preferences": "use bold provocative statements, avoid corporate jargon",
            },
            n_concepts=1,
            persist=False,
        )

        assert r_neutral.success
        assert r_aggressive.success
        print(f"\nNeutral   : {r_neutral.concepts[0].headline}")
        print(f"Aggressive: {r_aggressive.concepts[0].headline}")

    finally:
        db_module.DB_PATH = original


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.skipif(not _gemini_key_available(), reason="GEMINI_API_KEY not configured")
async def test_no_persist_does_not_write_to_db(sample_company, sample_signals, tmp_path):
    """persist=False should generate concepts but not touch the database."""
    import aiosqlite
    import backend.database as db_module
    from backend.agents.campaign_gen import run_campaign_agent
    from backend.database import init_db

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    try:
        await init_db(test_db)
        response = await run_campaign_agent(
            company=sample_company,
            signals=[sample_signals[0]],
            n_concepts=1,
            persist=False,
        )

        assert response.success

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM campaigns")
            count = (await cursor.fetchone())[0]

        assert count == 0, "persist=False should not write to DB"

    finally:
        db_module.DB_PATH = original
