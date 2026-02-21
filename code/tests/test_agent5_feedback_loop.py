"""
Tests for Agent 5 — Feedback Loop Agent (Meta-Agent)

Run:
    cd code
    pytest tests/test_agent5_feedback_loop.py -v

Two test layers:
  1. Unit tests  — no API key required (tools in isolation, in-memory DB)
  2. Integration — requires GEMINI_API_KEY in .env (marked @pytest.mark.integration)

Test coverage:
  - Tool functions for each of the three loops
  - Pydantic models (feedback.py)
  - DB round-trips via in-memory SQLite
  - Full agent run (integration only)
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
import aiosqlite

# ── Make backend importable from the code/ root ───────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import init_db, CREATE_TABLES_SQL
from backend.config import settings

# ── Agent 5 imports ───────────────────────────────────────────────────────────
from backend.agents.feedback_loop import (
    get_campaign_performance,
    compute_prompt_weights,
    save_prompt_weights,
    get_cross_company_metrics,
    extract_style_patterns,
    save_shared_pattern,
    get_signal_engagement_pairs,
    compute_calibration,
    save_calibration,
    run_feedback_loop,
    _db_path,
)
from backend.models.feedback import (
    CalibrationResult,
    FeedbackLoopResult,
    Loop1Result,
    Loop2Result,
    Loop3Result,
    PromptWeightUpdate,
    SharedPattern,
)

# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def tmp_db(tmp_path, monkeypatch):
    """Create a fresh in-memory SQLite database for each test."""
    db_file = tmp_path / "test_signal.db"

    # Patch the module-level DB_PATH so all tools use this temp DB
    import backend.database as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)

    async with aiosqlite.connect(db_file) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()

    return db_file


@pytest_asyncio.fixture
async def seeded_db(tmp_db):
    """
    Seed the temp DB with:
      - 1 company
      - 2 trend signals
      - 3 campaigns linked to the company + signals
      - 3 campaign_metrics rows
    """
    company_id = str(uuid.uuid4())
    signal_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    campaign_ids = [str(uuid.uuid4()) for _ in range(3)]

    async with aiosqlite.connect(tmp_db) as db:
        # Company
        await db.execute(
            """INSERT INTO companies (id, name, industry, tone_of_voice,
               target_audience, campaign_goals)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (company_id, "Acme Corp", "B2B SaaS", "professional",
             "CTOs and data engineers", "increase signups"),
        )

        # Trend signals
        for i, sig_id in enumerate(signal_ids):
            await db.execute(
                """INSERT INTO trend_signals (id, title, category,
                   probability, probability_momentum, volume, volume_velocity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sig_id, f"Signal {i}", "tech", 0.65 + i * 0.1,
                 0.05, 50000.0 + i * 10000, 1200.0 + i * 500),
            )

        # Campaigns
        channels = ["twitter", "linkedin", "twitter"]
        for i, camp_id in enumerate(campaign_ids):
            await db.execute(
                """INSERT INTO campaigns (id, company_id, trend_signal_id,
                   headline, body_copy, channel_recommendation,
                   channel_reasoning, confidence_score, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'posted')""",
                (camp_id, company_id, signal_ids[i % 2],
                 f"Headline {i}", f"Body copy for campaign {i} with enough words to be realistic content here.",
                 channels[i], "good fit", 0.7 + i * 0.05),
            )

        # Metrics
        eng_rates = [0.045, 0.082, 0.031]
        sentiments = [0.3, 0.6, -0.1]
        for i, (camp_id, eng, sent) in enumerate(zip(campaign_ids, eng_rates, sentiments)):
            await db.execute(
                """INSERT INTO campaign_metrics (id, campaign_id, channel,
                   impressions, clicks, engagement_rate, sentiment_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), camp_id, channels[i],
                 10000 + i * 5000, int((10000 + i * 5000) * eng),
                 eng, sent),
            )

        await db.commit()

    return {"db": tmp_db, "company_id": company_id, "signal_ids": signal_ids,
            "campaign_ids": campaign_ids}


# =============================================================================
# Model tests — no DB required
# =============================================================================

class TestFeedbackModels:
    def test_prompt_weight_update_valid(self):
        upd = PromptWeightUpdate(
            company_id="cmp-1",
            weight_key="tone_aggressive",
            weight_value=1.4,
            reasoning="High engagement on bold tone.",
        )
        assert upd.weight_key == "tone_aggressive"
        assert upd.weight_value == 1.4
        row = upd.to_db_row()
        assert "id" in row
        assert row["company_id"] == "cmp-1"
        assert row["agent_name"] == "campaign_gen"

    def test_prompt_weight_update_boundary(self):
        upd = PromptWeightUpdate(
            company_id="c", weight_key="k", weight_value=0.0
        )
        assert upd.weight_value == 0.0

        upd2 = PromptWeightUpdate(
            company_id="c", weight_key="k", weight_value=3.0
        )
        assert upd2.weight_value == 3.0

    def test_prompt_weight_out_of_range_raises(self):
        with pytest.raises(Exception):
            PromptWeightUpdate(company_id="c", weight_key="k", weight_value=5.0)

    def test_shared_pattern_to_db_row(self):
        p = SharedPattern(
            pattern_type="channel",
            description="LinkedIn wins for B2B",
            conditions={"industry": "B2B SaaS"},
            effect={"recommended_channel": "linkedin"},
            confidence=0.8,
            sample_size=25,
        )
        row = p.to_db_row()
        assert row["pattern_type"] == "channel"
        assert json.loads(row["conditions"])["industry"] == "B2B SaaS"
        assert json.loads(row["effect"])["recommended_channel"] == "linkedin"

    def test_calibration_result_to_db_row(self):
        cal = CalibrationResult(
            signal_category="crypto",
            probability_threshold=0.75,
            predicted_engagement=0.05,
            actual_engagement=0.048,
            accuracy_score=0.96,
            company_type="Fintech",
        )
        row = cal.to_db_row()
        assert row["signal_category"] == "crypto"
        assert row["accuracy_score"] == 0.96
        assert "id" in row

    def test_feedback_loop_result_structure(self):
        r = FeedbackLoopResult(
            loop1=Loop1Result(company_id="c1", campaigns_analyzed=5),
            loop2=Loop2Result(companies_analyzed=3),
            loop3=Loop3Result(signal_pairs_analyzed=10),
        )
        assert r.success is True
        assert r.loop1.campaigns_analyzed == 5
        assert r.loop3.signal_pairs_analyzed == 10


# =============================================================================
# Loop 1 Tool Tests
# =============================================================================

class TestLoop1Tools:
    def test_get_campaign_performance_empty_db(self, seeded_db):
        """Returns JSON with empty list for unknown company."""
        result = get_campaign_performance("nonexistent-company-id")
        data = json.loads(result)
        assert data["count"] == 0
        assert data["campaigns"] == []

    def test_get_campaign_performance_with_data(self, seeded_db):
        """Returns performance data for a seeded company."""
        company_id = seeded_db["company_id"]
        result = get_campaign_performance(company_id)
        data = json.loads(result)
        assert data["count"] == 3
        assert data["company_id"] == company_id
        for camp in data["campaigns"]:
            assert "engagement_rate" in camp
            assert "channel" in camp
            assert "headline" in camp

    def test_compute_prompt_weights_empty_input(self):
        """Empty campaigns → returns no weight updates."""
        perf_json = json.dumps({"company_id": "cmp-1", "campaigns": [], "count": 0})
        result = compute_prompt_weights(perf_json, "cmp-1")
        data = json.loads(result)
        assert data["weight_updates"] == []
        assert data["campaigns_analyzed"] == 0

    def test_compute_prompt_weights_invalid_json(self):
        result = compute_prompt_weights("not-valid-json", "cmp-1")
        data = json.loads(result)
        assert "error" in data

    def test_compute_prompt_weights_with_data(self, seeded_db):
        """With real performance data, should produce weight updates."""
        company_id = seeded_db["company_id"]
        perf_json = get_campaign_performance(company_id)
        result = compute_prompt_weights(perf_json, company_id)
        data = json.loads(result)
        assert data["company_id"] == company_id
        assert data["campaigns_analyzed"] == 3
        assert len(data["weight_updates"]) >= 1
        for upd in data["weight_updates"]:
            assert "weight_key" in upd
            assert "weight_value" in upd
            assert 0.0 <= upd["weight_value"] <= 3.0
            assert "reasoning" in upd

    def test_save_prompt_weights_persists_to_db(self, seeded_db):
        """Saved weights are readable from the DB."""
        company_id = seeded_db["company_id"]
        weights_json = json.dumps({
            "company_id": company_id,
            "weight_updates": [
                {"weight_key": "tone_aggressive", "weight_value": 1.5, "reasoning": "test"},
                {"weight_key": "hook_question", "weight_value": 1.2, "reasoning": "test"},
            ],
        })
        result = save_prompt_weights(weights_json)
        data = json.loads(result)
        assert data["success"] is True
        assert data["saved"] == 2

        # Verify DB
        async def _check():
            async with aiosqlite.connect(seeded_db["db"]) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT COUNT(*) AS cnt FROM prompt_weights WHERE company_id=?",
                    (company_id,),
                )
                row = await cur.fetchone()
                return row["cnt"]

        count = asyncio.get_event_loop().run_until_complete(_check())
        assert count == 2

    def test_save_prompt_weights_upsert(self, seeded_db):
        """Saving the same key twice updates rather than duplicating."""
        company_id = seeded_db["company_id"]
        weights_json = json.dumps({
            "company_id": company_id,
            "weight_updates": [{"weight_key": "tone_positive", "weight_value": 1.3, "reasoning": "first"}],
        })
        save_prompt_weights(weights_json)

        # Update the same key with a different value
        weights_json2 = json.dumps({
            "company_id": company_id,
            "weight_updates": [{"weight_key": "tone_positive", "weight_value": 1.7, "reasoning": "update"}],
        })
        save_prompt_weights(weights_json2)

        async def _check():
            async with aiosqlite.connect(seeded_db["db"]) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT weight_value FROM prompt_weights WHERE company_id=? AND weight_key='tone_positive'",
                    (company_id,),
                )
                row = await cur.fetchone()
                return row["weight_value"] if row else None

        val = asyncio.get_event_loop().run_until_complete(_check())
        assert val == pytest.approx(1.7, abs=0.01)

    def test_save_prompt_weights_empty_list(self):
        result = save_prompt_weights(json.dumps({"company_id": "c", "weight_updates": []}))
        data = json.loads(result)
        assert data["saved"] == 0
        assert data["success"] is True

    def test_save_prompt_weights_invalid_json(self):
        result = save_prompt_weights("bad json!")
        data = json.loads(result)
        assert data["success"] is False


# =============================================================================
# Loop 2 Tool Tests
# =============================================================================

class TestLoop2Tools:
    def test_get_cross_company_metrics_empty(self, tmp_db):
        """Empty DB returns empty list."""
        result = get_cross_company_metrics(min_campaigns=1)
        data = json.loads(result)
        assert data["companies"] == []

    def test_get_cross_company_metrics_with_data(self, seeded_db):
        """Returns aggregated rows from seeded data."""
        result = get_cross_company_metrics(min_campaigns=1)
        data = json.loads(result)
        assert len(data["companies"]) >= 1
        for row in data["companies"]:
            assert "industry" in row
            assert "avg_engagement" in row
            assert "channel" in row

    def test_extract_style_patterns_empty(self):
        """Empty metrics → no patterns."""
        metrics_json = json.dumps({"companies": [], "total_campaigns": 0})
        result = extract_style_patterns(metrics_json)
        data = json.loads(result)
        assert data["patterns"] == []

    def test_extract_style_patterns_invalid_json(self):
        result = extract_style_patterns("not json")
        data = json.loads(result)
        assert "error" in data or data["patterns"] == []

    def test_extract_style_patterns_with_data(self, seeded_db):
        """With seeded data, extracts at least one pattern."""
        metrics_json = get_cross_company_metrics(min_campaigns=1)
        result = extract_style_patterns(metrics_json)
        data = json.loads(result)
        assert isinstance(data["patterns"], list)
        for p in data["patterns"]:
            assert "pattern_type" in p
            assert "description" in p
            assert "confidence" in p
            assert 0.0 <= p["confidence"] <= 1.0

    def test_save_shared_pattern_persists(self, seeded_db):
        """Saved pattern appears in DB."""
        pattern_json = json.dumps({
            "pattern_type": "channel",
            "description": "LinkedIn wins for B2B SaaS at 8.2% engagement.",
            "conditions": {"industry": "B2B SaaS"},
            "effect": {"recommended_channel": "linkedin"},
            "confidence": 0.78,
            "sample_size": 12,
        })
        result = save_shared_pattern(pattern_json)
        data = json.loads(result)
        assert data["success"] is True
        assert "pattern_id" in data

        async def _check():
            async with aiosqlite.connect(seeded_db["db"]) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT COUNT(*) AS cnt FROM shared_patterns"
                )
                row = await cur.fetchone()
                return row["cnt"]

        count = asyncio.get_event_loop().run_until_complete(_check())
        assert count == 1

    def test_save_shared_pattern_invalid_json(self):
        result = save_shared_pattern("{{bad")
        data = json.loads(result)
        assert data["success"] is False


# =============================================================================
# Loop 3 Tool Tests
# =============================================================================

class TestLoop3Tools:
    def test_get_signal_engagement_pairs_empty(self, tmp_db):
        """Empty DB returns empty pairs."""
        result = get_signal_engagement_pairs()
        data = json.loads(result)
        assert data["count"] == 0
        assert data["pairs"] == []

    def test_get_signal_engagement_pairs_with_data(self, seeded_db):
        """Returns pairs from seeded data."""
        result = get_signal_engagement_pairs()
        data = json.loads(result)
        assert data["count"] >= 1
        for pair in data["pairs"]:
            assert "signal_category" in pair
            assert "probability" in pair
            assert "engagement_rate" in pair
            assert "company_type" in pair

    def test_compute_calibration_empty(self):
        """Empty pairs → no calibrations."""
        pairs_json = json.dumps({"pairs": [], "count": 0})
        result = compute_calibration(pairs_json)
        data = json.loads(result)
        assert data["calibrations"] == []

    def test_compute_calibration_invalid_json(self):
        result = compute_calibration("!!!")
        data = json.loads(result)
        assert "error" in data or data["calibrations"] == []

    def test_compute_calibration_with_data(self, seeded_db):
        """With seeded data, produces calibration entries."""
        pairs_json = get_signal_engagement_pairs()
        result = compute_calibration(pairs_json)
        data = json.loads(result)
        assert isinstance(data["calibrations"], list)
        for cal in data["calibrations"]:
            assert "signal_category" in cal
            assert "accuracy_score" in cal
            assert 0.0 <= cal["accuracy_score"] <= 1.0
            assert "predicted_engagement" in cal
            assert "actual_engagement" in cal

    def test_compute_calibration_accuracy_range(self):
        """Accuracy score is always in [0, 1] even for extreme inputs."""
        pairs_json = json.dumps({
            "pairs": [
                {
                    "signal_id": "s1", "signal_category": "crypto",
                    "probability": 0.9, "probability_momentum": 0.1,
                    "volume": 100000, "volume_velocity": 5000,
                    "company_type": "Fintech", "engagement_rate": 0.0001,
                    "impressions": 100,
                },
                {
                    "signal_id": "s2", "signal_category": "crypto",
                    "probability": 0.95, "probability_momentum": 0.15,
                    "volume": 200000, "volume_velocity": 8000,
                    "company_type": "Fintech", "engagement_rate": 0.0002,
                    "impressions": 200,
                },
            ],
            "count": 2,
        })
        result = compute_calibration(pairs_json)
        data = json.loads(result)
        for cal in data["calibrations"]:
            assert 0.0 <= cal["accuracy_score"] <= 1.0
            assert cal["predicted_engagement"] >= 0.0

    def test_save_calibration_persists(self, seeded_db):
        """Saved calibrations appear in DB."""
        calibrations_json = json.dumps({
            "calibrations": [
                {
                    "signal_category": "crypto",
                    "probability_threshold": 0.75,
                    "volume_velocity_threshold": 2500.0,
                    "predicted_engagement": 0.05,
                    "actual_engagement": 0.048,
                    "accuracy_score": 0.96,
                    "company_type": "Fintech",
                },
                {
                    "signal_category": "politics",
                    "probability_threshold": 0.6,
                    "volume_velocity_threshold": 1000.0,
                    "predicted_engagement": 0.03,
                    "actual_engagement": 0.04,
                    "accuracy_score": 0.75,
                    "company_type": "Media",
                },
            ]
        })
        result = save_calibration(calibrations_json)
        data = json.loads(result)
        assert data["success"] is True
        assert data["saved"] == 2

        async def _check():
            async with aiosqlite.connect(seeded_db["db"]) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute("SELECT COUNT(*) AS cnt FROM signal_calibration")
                row = await cur.fetchone()
                return row["cnt"]

        count = asyncio.get_event_loop().run_until_complete(_check())
        assert count == 2

    def test_save_calibration_empty(self):
        result = save_calibration(json.dumps({"calibrations": []}))
        data = json.loads(result)
        assert data["saved"] == 0
        assert data["success"] is True

    def test_save_calibration_invalid_json(self):
        result = save_calibration("not json")
        data = json.loads(result)
        assert data["success"] is False


# =============================================================================
# End-to-End Tool Pipeline Tests (no LLM)
# =============================================================================

class TestToolPipelines:
    """Test that tool chains work correctly without a real LLM."""

    def test_loop1_tool_chain(self, seeded_db):
        """Full Loop 1 pipeline: get → compute → save."""
        company_id = seeded_db["company_id"]

        perf_json = get_campaign_performance(company_id)
        weights_json = compute_prompt_weights(perf_json, company_id)
        save_result = save_prompt_weights(weights_json)

        perf = json.loads(perf_json)
        weights = json.loads(weights_json)
        saved = json.loads(save_result)

        assert perf["count"] == 3
        assert weights["campaigns_analyzed"] == 3
        assert saved["success"] is True
        assert saved["saved"] == len(weights["weight_updates"])

    def test_loop2_tool_chain(self, seeded_db):
        """Full Loop 2 pipeline: get → extract → save."""
        metrics_json = get_cross_company_metrics(min_campaigns=1)
        patterns_json = extract_style_patterns(metrics_json)
        patterns = json.loads(patterns_json)

        save_results = []
        for p in patterns.get("patterns", []):
            res = save_shared_pattern(json.dumps(p))
            save_results.append(json.loads(res))

        for res in save_results:
            assert res["success"] is True

    def test_loop3_tool_chain(self, seeded_db):
        """Full Loop 3 pipeline: get → compute → save."""
        pairs_json = get_signal_engagement_pairs()
        calibrations_json = compute_calibration(pairs_json)
        save_result = save_calibration(calibrations_json)

        saved = json.loads(save_result)
        assert saved["success"] is True

    def test_loop1_idempotent(self, seeded_db):
        """Running Loop 1 twice updates rather than duplicating rows."""
        company_id = seeded_db["company_id"]
        perf_json = get_campaign_performance(company_id)
        weights_json = compute_prompt_weights(perf_json, company_id)

        save_prompt_weights(weights_json)
        save_prompt_weights(weights_json)  # Run again — should upsert, not duplicate

        async def _count():
            async with aiosqlite.connect(seeded_db["db"]) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT COUNT(*) AS cnt FROM prompt_weights WHERE company_id=?",
                    (company_id,),
                )
                row = await cur.fetchone()
                return row["cnt"]

        count = asyncio.get_event_loop().run_until_complete(_count())
        weights = json.loads(weights_json)
        assert count == len(weights["weight_updates"])


# =============================================================================
# Integration Tests — require GEMINI_API_KEY
# =============================================================================

@pytest.mark.integration
class TestFeedbackLoopAgentIntegration:
    """Full end-to-end agent runs. Require GEMINI_API_KEY."""

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        if not settings.gemini_api_key_set:
            pytest.skip("GEMINI_API_KEY not set — skipping integration tests")

    @pytest.mark.asyncio
    async def test_run_loop2_and_loop3_only(self, seeded_db):
        """Run the full agent with only Loop 2 and Loop 3 (no company_id needed)."""
        result = await run_feedback_loop(
            company_id=None,
            run_loop1=False,
            run_loop2=True,
            run_loop3=True,
        )
        assert isinstance(result, FeedbackLoopResult)
        assert result.loop1 is None
        assert result.loop2 is not None
        assert result.loop3 is not None
        assert result.total_latency_ms is not None and result.total_latency_ms > 0

        # Skip assertion on success if quota was exhausted — API billing issue, not code bug
        if result.loop2.error and "RESOURCE_EXHAUSTED" in str(result.loop2.error):
            pytest.skip("Gemini API free-tier quota exhausted — re-run when quota resets")
        assert result.loop2.success is True
        assert result.loop3.success is True

    @pytest.mark.asyncio
    async def test_run_all_loops(self, seeded_db):
        """Run all three loops with a real company_id."""
        company_id = seeded_db["company_id"]
        result = await run_feedback_loop(
            company_id=company_id,
            run_loop1=True,
            run_loop2=True,
            run_loop3=True,
        )
        assert isinstance(result, FeedbackLoopResult)
        assert result.loop1 is not None
        assert result.loop1.company_id == company_id
        assert result.loop2 is not None
        assert result.loop3 is not None
        assert "Loop1" in result.overall_summary

        # Skip assertion on overall success if quota was exhausted
        quota_errors = [
            r for r in [result.loop1, result.loop2, result.loop3]
            if r and r.error and "RESOURCE_EXHAUSTED" in str(r.error)
        ]
        if quota_errors:
            pytest.skip("Gemini API free-tier quota exhausted — re-run when quota resets")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_loop1_only(self, seeded_db):
        """Loop 1 correctly scopes to the specified company."""
        company_id = seeded_db["company_id"]
        result = await run_feedback_loop(
            company_id=company_id,
            run_loop1=True,
            run_loop2=False,
            run_loop3=False,
        )
        assert result.loop1 is not None
        assert result.loop1.company_id == company_id
        assert result.loop2 is None
        assert result.loop3 is None

    @pytest.mark.asyncio
    async def test_run_no_data_graceful(self, tmp_db):
        """Agent handles empty DB gracefully — no crash."""
        result = await run_feedback_loop(
            company_id="nonexistent-id",
            run_loop1=True,
            run_loop2=True,
            run_loop3=True,
        )
        assert isinstance(result, FeedbackLoopResult)
        # Should succeed even with no data
        assert result.loop2 is not None
        assert result.loop3 is not None
