"""
Tests for Agent 6 — Content Strategy Agent

Test layers:
  1. Unit tests     — no API key required (models + tools in isolation)
  2. Integration    — DB persistence with temp SQLite
  3. End-to-end     — full ADK agent run (requires GEMINI_API_KEY)

Run all unit tests (no API key needed):
    cd code
    pytest tests/test_agent6_content_strategy.py -v -m unit

Run integration tests (no API key needed):
    pytest tests/test_agent6_content_strategy.py -v -m integration

Run e2e (requires GEMINI_API_KEY in .env):
    pytest tests/test_agent6_content_strategy.py -v -m e2e
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

_code_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_code_dir))

_here = Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from backend.models.content import (
    ContentStrategy,
    ContentStrategyResponse,
    ContentType,
    CONTENT_TYPE_META,
)
from backend.agents.content_strategy import (
    score_content_format,
    format_strategy_output,
    _build_instruction,
    _extract_strategies,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_strategy_input() -> dict:
    return {
        "content_type": "linkedin_article",
        "reasoning": "LinkedIn article reaches B2B professionals effectively.",
        "target_length": "800-1200 words",
        "tone_direction": "Professional, data-driven",
        "structure_outline": ["Hook", "Key insight", "Evidence", "CTA"],
        "priority_score": 0.85,
        "visual_needed": False,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — ContentType & ContentStrategy model
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestContentType:
    def test_all_types_defined(self):
        expected = {
            "tweet_thread", "linkedin_article", "blog_post", "video_script",
            "infographic", "newsletter", "instagram_carousel",
        }
        assert {t.value for t in ContentType} == expected

    def test_content_type_meta_has_all_types(self):
        for ct in ContentType:
            assert ct.value in CONTENT_TYPE_META
            meta = CONTENT_TYPE_META[ct.value]
            assert "label" in meta
            assert "channel" in meta
            assert "typical_length" in meta
            assert "visual_required" in meta


@pytest.mark.unit
class TestContentStrategyModel:
    def test_valid_strategy_creation(self, sample_strategy_input):
        strat = ContentStrategy(
            campaign_id="camp-001",
            company_id="co-001",
            content_type=ContentType.LINKEDIN_ARTICLE,
            reasoning=sample_strategy_input["reasoning"],
            target_length=sample_strategy_input["target_length"],
            tone_direction=sample_strategy_input["tone_direction"],
            structure_outline=sample_strategy_input["structure_outline"],
            priority_score=sample_strategy_input["priority_score"],
            visual_needed=sample_strategy_input["visual_needed"],
        )
        assert strat.campaign_id == "camp-001"
        assert strat.content_type == ContentType.LINKEDIN_ARTICLE
        assert strat.priority_score == 0.85
        assert strat.id

    def test_priority_score_bounds(self):
        with pytest.raises(Exception):
            ContentStrategy(
                campaign_id="c", company_id="co",
                content_type=ContentType.BLOG_POST,
                reasoning="r", target_length="t", tone_direction="t",
                priority_score=1.5,
            )

    def test_to_db_row_serializes_outline(self):
        strat = ContentStrategy(
            campaign_id="c", company_id="co",
            content_type=ContentType.TWEET_THREAD,
            reasoning="r", target_length="5 tweets", tone_direction="bold",
            structure_outline=["Hook", "Point 1", "CTA"],
        )
        row = strat.to_db_row()
        assert "structure_outline" in row
        parsed = json.loads(row["structure_outline"])
        assert parsed == ["Hook", "Point 1", "CTA"]
        assert row["visual_needed"] in (0, 1)

    def test_from_db_row_round_trip(self):
        strat = ContentStrategy(
            campaign_id="c1", company_id="co1",
            content_type=ContentType.NEWSLETTER,
            reasoning="Email list is warm", target_length="600 words",
            tone_direction="conversational",
            structure_outline=["Intro", "Main", "Sign-off"],
        )
        row = strat.to_db_row()
        restored = ContentStrategy.from_db_row(row)
        assert restored.id == strat.id
        assert restored.content_type == strat.content_type
        assert restored.structure_outline == strat.structure_outline


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — score_content_format tool
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestScoreContentFormat:
    def test_valid_input_returns_composite_score(self):
        result = json.loads(score_content_format(
            content_type="linkedin_article",
            audience_fit=0.9,
            channel_alignment=0.85,
            production_complexity=0.3,
            reasoning="B2B audience fits LinkedIn",
        ))
        assert result["is_valid"] is True
        assert result["content_type"] == "linkedin_article"
        assert 0.0 <= result["composite_score"] <= 1.0
        assert result["issues"] == []

    def test_unknown_content_type_adds_issue(self):
        result = json.loads(score_content_format(
            content_type="podcast_script",
            audience_fit=0.8,
            channel_alignment=0.7,
            production_complexity=0.5,
            reasoning="test",
        ))
        assert result["is_valid"] is False
        assert "podcast_script" in str(result["issues"])

    def test_out_of_range_scores_add_issues(self):
        result = json.loads(score_content_format(
            content_type="blog_post",
            audience_fit=1.5,
            channel_alignment=0.5,
            production_complexity=0.2,
            reasoning="test",
        ))
        assert result["is_valid"] is False
        assert any("audience_fit" in i for i in result["issues"])

    def test_low_complexity_boosts_composite(self):
        low = json.loads(score_content_format(
            "blog_post", 0.8, 0.8, 0.1, "easy"
        ))
        high = json.loads(score_content_format(
            "blog_post", 0.8, 0.8, 0.9, "hard"
        ))
        assert low["composite_score"] > high["composite_score"]


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — format_strategy_output tool
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFormatStrategyOutput:
    def test_valid_json_array_produces_strategies(self, sample_strategy_input):
        raw = json.dumps([sample_strategy_input])
        result = json.loads(format_strategy_output(raw, "camp-001", "co-001"))
        assert result["count"] == 1
        assert result["campaign_id"] == "camp-001"
        strat = result["strategies"][0]
        assert strat["content_type"] == "linkedin_article"
        assert strat["campaign_id"] == "camp-001"
        assert strat["company_id"] == "co-001"

    def test_wrapped_dict_with_strategies_key(self, sample_strategy_input):
        raw = json.dumps({"strategies": [sample_strategy_input]})
        result = json.loads(format_strategy_output(raw, "camp-002", "co-002"))
        assert result["count"] == 1
        assert result["strategies"][0]["campaign_id"] == "camp-002"

    def test_invalid_json_returns_error(self):
        result = json.loads(format_strategy_output("not json {{{", "c", "co"))
        assert "error" in result
        assert result["count"] == 0

    def test_unknown_content_type_falls_back_to_blog_post(self):
        inp = {"content_type": "unknown_format", "reasoning": "r",
               "target_length": "t", "tone_direction": "t"}
        result = json.loads(format_strategy_output(
            json.dumps([inp]), "c", "co"
        ))
        assert result["count"] == 1
        assert result["strategies"][0]["content_type"] == "blog_post"

    def test_structure_outline_string_parsed_to_list(self):
        inp = {
            "content_type": "tweet_thread",
            "reasoning": "r", "target_length": "5", "tone_direction": "t",
            "structure_outline": "Hook, Data, CTA",
        }
        result = json.loads(format_strategy_output(
            json.dumps([inp]), "c", "co"
        ))
        assert result["strategies"][0]["structure_outline"] == ["Hook", "Data", "CTA"]


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — _build_instruction
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBuildInstruction:
    def test_contains_company_context(self):
        inst = _build_instruction(
            "Acme", "SaaS", "professional", "CTOs", "lead gen"
        )
        assert "Acme" in inst
        assert "SaaS" in inst
        assert "CTOs" in inst
        assert "lead gen" in inst

    def test_contains_content_type_catalog(self):
        inst = _build_instruction("X", "Y", "Z", "A", "B")
        assert "tweet_thread" in inst or "Tweet Thread" in inst
        assert "linkedin_article" in inst or "LinkedIn" in inst


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — _extract_strategies
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestExtractStrategies:
    def test_extracts_from_json_code_block(self, sample_strategy_input):
        payload = json.dumps({"strategies": [sample_strategy_input]})
        text = f"Here are the strategies:\n```json\n{payload}\n```"
        result = _extract_strategies(text, "camp-1", "co-1")
        assert len(result) == 1
        assert result[0].content_type == ContentType.LINKEDIN_ARTICLE

    def test_returns_empty_on_no_json(self):
        result = _extract_strategies("No JSON here.", "c", "co")
        assert result == []


# ──────────────────────────────────────────────────────────────────────────────
# Integration Tests — DB persistence
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_persist_strategies_writes_to_db(tmp_path):
    import aiosqlite
    import backend.database as db_module
    from backend.database import init_db
    from backend.agents.content_strategy import _persist_strategies

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    try:
        await init_db(test_db)
        strategies = [
            ContentStrategy(
                campaign_id="camp-1",
                company_id="co-1",
                content_type=ContentType.BLOG_POST,
                reasoning="Blog fits SEO goals",
                target_length="1200 words",
                tone_direction="authoritative",
                structure_outline=["Intro", "Body", "Conclusion"],
                priority_score=0.8,
            ),
        ]
        await _persist_strategies(strategies)

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM content_strategies"
            )
            count = (await cursor.fetchone())[0]
        assert count == 1
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
async def test_full_agent_run_returns_strategies(tmp_path):
    import backend.database as db_module
    from backend.agents.content_strategy import run_content_strategy_agent

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    try:
        response = await run_content_strategy_agent(
            campaign_id="test-camp-001",
            company_id="test-co-001",
            headline="AI Coding Tools Won't Replace You — They'll Make You Dangerous",
            body_copy="As prediction markets signal rising confidence in AI augmentation over replacement, now is the time to position your developer tools brand.",
            channel_recommendation="linkedin",
            company_name="NovaTech",
            industry="SaaS / Developer Tools",
            tone="bold, technical",
            audience="software engineers",
            goals="drive sign-ups",
            persist=False,
        )

        assert isinstance(response, ContentStrategyResponse)
        assert response.success
        assert len(response.strategies) >= 1
        assert response.latency_ms > 0

        for s in response.strategies:
            assert isinstance(s, ContentStrategy)
            assert s.content_type in ContentType
            assert 0.0 <= s.priority_score <= 1.0
            assert s.campaign_id == "test-camp-001"
    finally:
        db_module.DB_PATH = original
