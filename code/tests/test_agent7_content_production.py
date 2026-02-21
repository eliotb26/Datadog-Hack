"""
Tests for Agent 7 — Content Production Agent

Test layers:
  1. Unit tests     — no API key required (models + tools in isolation)
  2. Integration    — DB persistence with temp SQLite
  3. End-to-end     — full ADK agent run (requires GEMINI_API_KEY)

Run all unit tests (no API key needed):
    cd code
    pytest tests/test_agent7_content_production.py -v -m unit

Run integration tests (no API key needed):
    pytest tests/test_agent7_content_production.py -v -m integration

Run e2e (requires GEMINI_API_KEY in .env):
    pytest tests/test_agent7_content_production.py -v -m e2e
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
    ContentPiece,
    ContentProductionResponse,
    ContentStrategy,
    ContentType,
)
from backend.agents.content_production import (
    validate_content_piece,
    format_content_output,
    _build_instruction,
    _extract_pieces,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_strategy() -> ContentStrategy:
    return ContentStrategy(
        id="strat-001",
        campaign_id="camp-001",
        company_id="co-001",
        content_type=ContentType.TWEET_THREAD,
        reasoning="Twitter thread for tech audience",
        target_length="5-tweet thread",
        tone_direction="Bold, data-backed",
        structure_outline=["Hook", "Data point", "Insight", "CTA"],
        priority_score=0.85,
        visual_needed=False,
    )


@pytest.fixture
def sample_piece_input() -> dict:
    return {
        "content_type": "tweet_thread",
        "title": "AI Tools Make You Dangerous",
        "body": "[1/5] AI coding tools won't replace you — they'll make you dangerous.\n[2/5] Here's the data...",
        "summary": "Thread on AI augmentation",
        "word_count": 45,
        "quality_score": 0.9,
        "brand_alignment": 0.85,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — ContentPiece model
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestContentPieceModel:
    def test_valid_piece_creation(self, sample_piece_input, sample_strategy):
        piece = ContentPiece(
            strategy_id=sample_strategy.id,
            campaign_id=sample_strategy.campaign_id,
            company_id=sample_strategy.company_id,
            content_type=ContentType.TWEET_THREAD,
            title=sample_piece_input["title"],
            body=sample_piece_input["body"],
            summary=sample_piece_input["summary"],
            word_count=sample_piece_input["word_count"],
            quality_score=sample_piece_input["quality_score"],
            brand_alignment=sample_piece_input["brand_alignment"],
        )
        assert piece.strategy_id == "strat-001"
        assert piece.title == "AI Tools Make You Dangerous"
        assert piece.quality_score == 0.9
        assert piece.id

    def test_quality_score_bounds(self, sample_strategy):
        with pytest.raises(Exception):
            ContentPiece(
                strategy_id=sample_strategy.id,
                campaign_id=sample_strategy.campaign_id,
                company_id=sample_strategy.company_id,
                content_type=ContentType.BLOG_POST,
                title="T", body="Body with enough content to pass validation " * 5,
                quality_score=1.5,
            )

    def test_to_db_row_contains_required_keys(self, sample_piece_input, sample_strategy):
        piece = ContentPiece(
            strategy_id=sample_strategy.id,
            campaign_id=sample_strategy.campaign_id,
            company_id=sample_strategy.company_id,
            content_type=ContentType.BLOG_POST,
            title="Test", body="Body " * 100,
        )
        row = piece.to_db_row()
        for key in ("id", "strategy_id", "campaign_id", "title", "body", "status"):
            assert key in row

    def test_from_db_row_round_trip(self, sample_piece_input, sample_strategy):
        piece = ContentPiece(
            strategy_id=sample_strategy.id,
            campaign_id=sample_strategy.campaign_id,
            company_id=sample_strategy.company_id,
            content_type=ContentType.NEWSLETTER,
            title="Newsletter Title",
            body="Full newsletter body with enough words to be valid content.",
            word_count=50,
        )
        row = piece.to_db_row()
        restored = ContentPiece.from_db_row(row)
        assert restored.id == piece.id
        assert restored.title == piece.title


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — validate_content_piece tool
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestValidateContentPiece:
    def test_valid_content_passes(self):
        result = json.loads(validate_content_piece(
            content_type="blog_post",
            title="Valid Title",
            body="This is a valid body with more than fifty characters to pass the minimum length check.",
            word_count=500,
        ))
        assert result["is_valid"] is True
        assert result["issues"] == []
        assert result["quality_score"] >= 0.9

    def test_empty_title_fails(self):
        result = json.loads(validate_content_piece(
            content_type="blog_post",
            title="",
            body="A" * 100,
            word_count=50,
        ))
        assert result["is_valid"] is False
        assert any("title" in i.lower() for i in result["issues"])

    def test_short_body_fails(self):
        result = json.loads(validate_content_piece(
            content_type="blog_post",
            title="Title",
            body="Short",
            word_count=5,
        ))
        assert result["is_valid"] is False
        assert any("short" in i.lower() or "50" in i for i in result["issues"])

    def test_placeholder_text_fails(self):
        result = json.loads(validate_content_piece(
            content_type="blog_post",
            title="Title",
            body="Lorem ipsum dolor sit amet " * 5,
            word_count=50,
        ))
        assert result["is_valid"] is False
        assert any("placeholder" in i.lower() or "lorem" in i.lower() for i in result["issues"])

    def test_blog_post_too_short(self):
        result = json.loads(validate_content_piece(
            content_type="blog_post",
            title="Title",
            body="Short blog " * 30,
            word_count=250,
        ))
        assert result["is_valid"] is False
        assert any("300" in i or "short" in i.lower() for i in result["issues"])

    def test_linkedin_article_too_short(self):
        result = json.loads(validate_content_piece(
            content_type="linkedin_article",
            title="Title",
            body="Short " * 30,
            word_count=150,
        ))
        assert result["is_valid"] is False


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — format_content_output tool
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFormatContentOutput:
    def test_valid_json_produces_pieces(self, sample_piece_input, sample_strategy):
        raw = json.dumps([sample_piece_input])
        result = json.loads(format_content_output(
            raw, sample_strategy.id, sample_strategy.campaign_id, sample_strategy.company_id
        ))
        assert result["count"] == 1
        assert result["strategy_id"] == sample_strategy.id
        piece = result["pieces"][0]
        assert piece["content_type"] == "tweet_thread"
        assert piece["campaign_id"] == sample_strategy.campaign_id
        assert piece["title"] == sample_piece_input["title"]

    def test_wrapped_dict_with_pieces_key(self, sample_piece_input, sample_strategy):
        raw = json.dumps({"pieces": [sample_piece_input]})
        result = json.loads(format_content_output(
            raw, "strat-1", "camp-1", "co-1"
        ))
        assert result["count"] == 1

    def test_content_pieces_key_alias(self, sample_piece_input, sample_strategy):
        raw = json.dumps({"content_pieces": [sample_piece_input]})
        result = json.loads(format_content_output(raw, "s", "c", "co"))
        assert result["count"] == 1

    def test_invalid_json_returns_error(self, sample_strategy):
        result = json.loads(format_content_output(
            "not json {{{",
            sample_strategy.id,
            sample_strategy.campaign_id,
            sample_strategy.company_id,
        ))
        assert "error" in result
        assert result["count"] == 0

    def test_body_as_list_serialized_to_string(self, sample_strategy):
        inp = {
            "content_type": "tweet_thread",
            "title": "Thread",
            "body": ["Tweet 1", "Tweet 2", "Tweet 3"],
        }
        result = json.loads(format_content_output(
            json.dumps([inp]), sample_strategy.id, "c", "co"
        ))
        assert result["count"] == 1
        body = result["pieces"][0]["body"]
        assert "Tweet 1" in body


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — _build_instruction
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestBuildInstruction:
    def test_contains_company_context(self, sample_strategy):
        inst = _build_instruction(
            "Acme", "professional", "CTOs", "lead gen",
            sample_strategy.content_type.value,
            sample_strategy.target_length,
            sample_strategy.tone_direction,
            sample_strategy.structure_outline,
        )
        assert "Acme" in inst
        assert "professional" in inst
        assert "CTOs" in inst

    def test_contains_structure_outline(self, sample_strategy):
        inst = _build_instruction(
            "X", "Y", "Z", "G",
            "blog_post", "1000 words", "formal",
            ["Intro", "Body", "Conclusion"],
        )
        assert "Intro" in inst
        assert "Body" in inst
        assert "Conclusion" in inst


# ──────────────────────────────────────────────────────────────────────────────
# Unit Tests — _extract_pieces
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestExtractPieces:
    def test_extracts_from_json_code_block(self, sample_piece_input, sample_strategy):
        payload = json.dumps({"pieces": [sample_piece_input]})
        text = f"Here is the content:\n```json\n{payload}\n```"
        result = _extract_pieces(text, sample_strategy)
        assert len(result) == 1
        assert result[0].content_type == ContentType.TWEET_THREAD
        assert result[0].title == sample_piece_input["title"]

    def test_returns_empty_on_no_json(self, sample_strategy):
        result = _extract_pieces("No JSON here.", sample_strategy)
        assert result == []


# ──────────────────────────────────────────────────────────────────────────────
# Integration Tests — DB persistence (mock _attach_media_assets)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_persist_pieces_writes_to_db(tmp_path, sample_strategy):
    import aiosqlite
    import backend.database as db_module
    from backend.database import init_db
    from backend.agents.content_production import _persist_pieces

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    try:
        await init_db(test_db)
        pieces = [
            ContentPiece(
                strategy_id=sample_strategy.id,
                campaign_id=sample_strategy.campaign_id,
                company_id=sample_strategy.company_id,
                content_type=ContentType.BLOG_POST,
                title="Test Blog",
                body="Full blog body with enough content to be valid. " * 50,
                word_count=500,
            ),
        ]
        await _persist_pieces(pieces)

        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM content_pieces")
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
async def test_full_agent_run_returns_pieces(tmp_path, sample_strategy):
    from unittest.mock import patch
    import backend.database as db_module
    from backend.config import settings
    from backend.agents.content_production import run_content_production_agent

    test_db = tmp_path / "signal.db"
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db

    # Disable media generation for faster e2e test
    with patch.object(settings, "ENABLE_GEMINI_MEDIA", False):
        try:
            response = await run_content_production_agent(
                strategy=sample_strategy,
                campaign_headline="AI Coding Tools Won't Replace You",
                campaign_body_copy="As prediction markets signal rising confidence in AI augmentation over replacement.",
                company_name="NovaTech",
                tone="bold, technical",
                audience="software engineers",
                goals="drive sign-ups",
                persist=False,
            )

            assert isinstance(response, ContentProductionResponse)
            assert response.success
            assert len(response.pieces) >= 1
            assert response.latency_ms > 0

            for p in response.pieces:
                assert isinstance(p, ContentPiece)
                assert p.content_type in ContentType
                assert p.title
                assert len(p.body) >= 50
                assert p.strategy_id == sample_strategy.id
        finally:
            db_module.DB_PATH = original
