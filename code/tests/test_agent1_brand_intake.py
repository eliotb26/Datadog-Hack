"""
Tests for Agent 1 — Brand Intake Agent

Run:
    cd code
    pytest tests/test_agent1_brand_intake.py -v

Two test layers:
  1. Unit tests — no API key required (model/DB/tools in isolation)
  2. Integration test — requires GEMINI_API_KEY set in .env (marked with @pytest.mark.integration)
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Make backend importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.models.company import CompanyProfile, CompanyProfileInput
from backend.agents.brand_intake import (
    validate_brand_profile,
    save_company_profile,
    _build_intake_message,
    run_brand_intake,
)
from backend.database import init_db, DB_PATH
from backend.config import settings


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_intake() -> CompanyProfileInput:
    return CompanyProfileInput(
        name="Acme Analytics",
        industry="B2B SaaS",
        tone_of_voice="professional yet approachable, data-driven",
        target_audience="Data engineers and analytics leads at Series B+ startups",
        campaign_goals="increase free trial signups and reduce time-to-activation",
        competitors=["Tableau", "Looker", "Metabase"],
        content_history=[
            "Thought leadership on data stack modernization",
            "Product walkthroughs for the modern data team",
        ],
        visual_style="clean, minimal, blue/white palette",
    )


@pytest.fixture
def minimal_intake() -> CompanyProfileInput:
    """Bare-minimum intake — only required fields."""
    return CompanyProfileInput(
        name="TinyStartup",
        industry="Fintech",
    )


# ──────────────────────────────────────────────────────────────
# Unit Tests — no API key needed
# ──────────────────────────────────────────────────────────────

class TestValidateBrandProfile:
    def test_valid_profile_passes(self):
        result = validate_brand_profile(
            name="Acme",
            industry="SaaS",
            tone_of_voice="professional",
            target_audience="CTOs",
            campaign_goals="lead gen",
        )
        assert result["is_valid"] is True
        assert result["missing_fields"] == []

    def test_missing_name_fails(self):
        result = validate_brand_profile(
            name="",
            industry="SaaS",
            tone_of_voice="professional",
            target_audience="CTOs",
            campaign_goals="lead gen",
        )
        assert result["is_valid"] is False
        assert "name" in result["missing_fields"]

    def test_multiple_missing_fields(self):
        result = validate_brand_profile(
            name="Acme",
            industry="",
            tone_of_voice="",
            target_audience="CTOs",
            campaign_goals="lead gen",
        )
        assert result["is_valid"] is False
        assert set(result["missing_fields"]) == {"industry", "tone_of_voice"}


class TestCompanyProfileModel:
    def test_profile_creation(self, sample_intake):
        profile = CompanyProfile(
            name=sample_intake.name,
            industry=sample_intake.industry,
            tone_of_voice=sample_intake.tone_of_voice,
            target_audience=sample_intake.target_audience,
            campaign_goals=sample_intake.campaign_goals,
            competitors=sample_intake.competitors or [],
            content_history=sample_intake.content_history or [],
        )
        assert profile.name == "Acme Analytics"
        assert profile.industry == "B2B SaaS"
        assert len(profile.competitors) == 3
        assert profile.id  # UUID assigned

    def test_to_db_row_serializes_json(self, sample_intake):
        profile = CompanyProfile(
            name=sample_intake.name,
            industry=sample_intake.industry,
            tone_of_voice=sample_intake.tone_of_voice or "",
            target_audience=sample_intake.target_audience or "",
            campaign_goals=sample_intake.campaign_goals or "",
            competitors=sample_intake.competitors or [],
        )
        row = profile.to_db_row()
        # Competitors must be JSON string in DB
        competitors_parsed = json.loads(row["competitors"])
        assert isinstance(competitors_parsed, list)
        assert "Tableau" in competitors_parsed

    def test_safety_threshold_defaults_to_0_7(self):
        profile = CompanyProfile(
            name="X",
            industry="Y",
            tone_of_voice="z",
            target_audience="a",
            campaign_goals="b",
        )
        assert profile.safety_threshold == 0.7

    def test_safety_threshold_validation(self):
        with pytest.raises(Exception):
            CompanyProfile(
                name="X", industry="Y", tone_of_voice="z",
                target_audience="a", campaign_goals="b",
                safety_threshold=1.5,  # out of range
            )


class TestBuildIntakeMessage:
    def test_message_contains_company_name(self, sample_intake):
        msg = _build_intake_message(sample_intake)
        assert "Acme Analytics" in msg

    def test_message_contains_all_fields(self, sample_intake):
        msg = _build_intake_message(sample_intake)
        assert "B2B SaaS" in msg
        assert "data-driven" in msg
        assert "Tableau" in msg

    def test_minimal_intake_message(self, minimal_intake):
        msg = _build_intake_message(minimal_intake)
        assert "TinyStartup" in msg
        assert "Fintech" in msg


class TestDatabaseInit:
    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, tmp_path):
        """DB init should create companies table."""
        import aiosqlite
        from backend.database import init_db, CREATE_TABLES_SQL

        test_db = tmp_path / "test_signal.db"
        # Monkeypatch DB_PATH for this test
        import backend.database as db_module
        original = db_module.DB_PATH
        db_module.DB_PATH = test_db
        try:
            await init_db(test_db)
            async with aiosqlite.connect(test_db) as db:
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = [row[0] for row in await cursor.fetchall()]
            expected = ["companies", "trend_signals", "campaigns", "campaign_metrics",
                        "prompt_weights", "shared_patterns", "signal_calibration", "agent_traces"]
            for table in expected:
                assert table in tables, f"Missing table: {table}"
        finally:
            db_module.DB_PATH = original


class TestSaveCompanyProfile:
    @pytest.mark.asyncio
    async def test_save_creates_record(self, tmp_path):
        """save_company_profile tool should persist a record to SQLite."""
        import aiosqlite
        import backend.database as db_module

        test_db = tmp_path / "signal.db"
        original = db_module.DB_PATH
        db_module.DB_PATH = test_db

        try:
            await init_db(test_db)

            result = save_company_profile(
                name="TestCo",
                industry="SaaS",
                tone_of_voice="bold",
                target_audience="developers",
                campaign_goals="signups",
                competitors='["CompA", "CompB"]',
            )

            assert result["name"] == "TestCo"
            company_id = result["company_id"]
            assert company_id  # non-empty UUID

            # Verify it's in the DB
            async with aiosqlite.connect(test_db) as db:
                cursor = await db.execute(
                    "SELECT name, industry FROM companies WHERE id = ?",
                    (company_id,),
                )
                row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "TestCo"
            assert row[1] == "SaaS"

        finally:
            db_module.DB_PATH = original


# ──────────────────────────────────────────────────────────────
# Integration Test — requires real GEMINI_API_KEY
# ──────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestBrandIntakeAgentLive:
    @pytest.mark.asyncio
    async def test_full_agent_run(self, sample_intake, tmp_path):
        """Full end-to-end: Agent 1 processes intake, saves profile to DB."""
        if not settings.gemini_api_key_set:
            pytest.skip("GEMINI_API_KEY not set — skipping live agent test")

        import backend.database as db_module
        test_db = tmp_path / "signal.db"
        original = db_module.DB_PATH
        db_module.DB_PATH = test_db

        try:
            result = await run_brand_intake(sample_intake)

            assert result["success"] is True, f"Agent failed. Response: {result['agent_response']}"
            assert result["company_id"] is not None
            assert result["latency_ms"] > 0
            assert len(result["agent_response"]) > 10

            # Verify record is in DB
            import aiosqlite
            async with aiosqlite.connect(test_db) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM companies")
                count = (await cursor.fetchone())[0]
            assert count == 1

        finally:
            db_module.DB_PATH = original
