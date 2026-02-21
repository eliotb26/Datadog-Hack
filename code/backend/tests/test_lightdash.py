"""Tests for the Lightdash integration.

Covers:
- LightdashClient stub mode (no env vars set)
- LightdashClient API calls via httpx mocking
- lightdash_metrics fallback to SQLite
- lightdash_metrics with a mocked LightdashClient
- FastAPI router endpoints
- Webhook signature & routing logic
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
import pytest_asyncio
from httpx import AsyncClient, Response

# ---------------------------------------------------------------------------
# Ensure no live Lightdash env vars bleed in during tests
# ---------------------------------------------------------------------------

os.environ.pop("LIGHTDASH_URL", None)
os.environ.pop("LIGHTDASH_API_KEY", None)
os.environ.pop("LIGHTDASH_PROJECT_UUID", None)

from code.backend.integrations.lightdash_client import LightdashClient  # noqa: E402
from code.backend.integrations.lightdash_metrics import (  # noqa: E402
    _days_ago,
    _query_sqlite,
    get_campaign_performance,
    get_agent_learning_curve,
    get_polymarket_calibration,
    get_channel_performance,
    get_cross_company_patterns,
    get_safety_metrics,
    get_analytics_embed_urls,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest_asyncio.fixture
async def tmp_db(tmp_path: Path) -> Path:
    """Create a minimal signal.db in a temp directory for fallback tests."""
    db_path = tmp_path / "signal.db"
    async with aiosqlite.connect(db_path) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                company_id TEXT,
                trend_signal_id TEXT,
                headline TEXT NOT NULL,
                body_copy TEXT NOT NULL,
                channel_recommendation TEXT,
                confidence_score REAL,
                safety_score REAL,
                safety_passed BOOLEAN DEFAULT 1,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS campaign_metrics (
                id TEXT PRIMARY KEY,
                campaign_id TEXT,
                channel TEXT,
                impressions INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0.0,
                sentiment_score REAL,
                measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_traces (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                braintrust_trace_id TEXT,
                company_id TEXT,
                quality_score REAL,
                tokens_used INTEGER,
                latency_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS signal_calibration (
                id TEXT PRIMARY KEY,
                signal_category TEXT,
                probability_threshold REAL,
                volume_velocity_threshold REAL,
                predicted_engagement REAL,
                actual_engagement REAL,
                accuracy_score REAL,
                calibrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS shared_patterns (
                id TEXT PRIMARY KEY,
                pattern_type TEXT,
                description TEXT,
                conditions TEXT,
                effect TEXT,
                confidence REAL,
                sample_size INTEGER,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Seed campaigns
        await db.execute("""
            INSERT INTO campaigns (id, company_id, headline, body_copy,
                channel_recommendation, confidence_score, safety_score, safety_passed)
            VALUES
                ('c1', 'comp1', 'Test Headline 1', 'Body copy 1', 'twitter', 0.85, 0.9, 1),
                ('c2', 'comp1', 'Test Headline 2', 'Body copy 2', 'linkedin', 0.72, 0.65, 1),
                ('c3', 'comp2', 'Test Headline 3', 'Body copy 3', 'email',   0.60, 0.2, 0)
        """)
        # Seed campaign_metrics
        await db.execute("""
            INSERT INTO campaign_metrics (id, campaign_id, channel, impressions, clicks, engagement_rate, sentiment_score)
            VALUES
                ('m1', 'c1', 'twitter',  1000, 50, 0.05, 0.8),
                ('m2', 'c2', 'linkedin',  500, 25, 0.05, 0.7),
                ('m3', 'c3', 'email',    2000, 40, 0.02, 0.3)
        """)
        # Seed agent_traces
        await db.execute("""
            INSERT INTO agent_traces (id, agent_name, quality_score, latency_ms)
            VALUES
                ('t1', 'campaign_gen', 0.7, 1200),
                ('t2', 'campaign_gen', 0.8, 1100),
                ('t3', 'trend_intel',  0.9,  800)
        """)
        # Seed signal_calibration
        await db.execute("""
            INSERT INTO signal_calibration
                (id, signal_category, probability_threshold, predicted_engagement, actual_engagement, accuracy_score)
            VALUES
                ('sc1', 'politics', 0.6, 0.05, 0.048, 0.96),
                ('sc2', 'sports',   0.7, 0.07, 0.062, 0.89)
        """)
        # Seed shared_patterns
        await db.execute("""
            INSERT INTO shared_patterns (id, pattern_type, description, confidence, sample_size)
            VALUES
                ('p1', 'tone',    'Conversational tone drives higher Twitter engagement', 0.82, 150),
                ('p2', 'channel', 'B2B brands perform 2x better on LinkedIn vs Twitter',  0.91, 200)
        """)
        await db.commit()
    return db_path


# ===========================================================================
# LightdashClient — stub mode (no env vars)
# ===========================================================================

class TestLightdashClientStubMode:
    """When LIGHTDASH_URL is not set the client must not raise — it stubs out."""

    def test_is_not_available(self) -> None:
        client = LightdashClient()
        assert client.is_available is False

    @pytest.mark.asyncio
    async def test_list_projects_returns_empty(self) -> None:
        async with LightdashClient() as client:
            assert await client.list_projects() == []

    @pytest.mark.asyncio
    async def test_list_dashboards_returns_empty(self) -> None:
        async with LightdashClient() as client:
            assert await client.list_dashboards() == []

    @pytest.mark.asyncio
    async def test_get_chart_results_returns_empty_structure(self) -> None:
        async with LightdashClient() as client:
            result = await client.get_chart_results("some-uuid")
        assert result == {"rows": [], "fields": {}}

    @pytest.mark.asyncio
    async def test_run_metric_query_returns_empty(self) -> None:
        async with LightdashClient() as client:
            result = await client.run_metric_query(
                explore_name="campaigns",
                dimensions=["campaigns_created_at_date"],
                metrics=["campaigns_avg_confidence_score"],
            )
        assert result == {"rows": [], "fields": {}}

    @pytest.mark.asyncio
    async def test_create_alert_returns_empty(self) -> None:
        async with LightdashClient() as client:
            result = await client.create_alert(
                saved_chart_uuid="uuid",
                name="test alert",
                threshold=0.3,
            )
        assert result == {}

    @pytest.mark.asyncio
    async def test_health_check_returns_false(self) -> None:
        async with LightdashClient() as client:
            assert await client.health_check() is False

    def test_embed_url_empty_when_not_configured(self) -> None:
        client = LightdashClient()
        assert client.get_dashboard_embed_url("some-uuid") == ""
        assert client.get_chart_embed_url("some-uuid") == ""


# ===========================================================================
# LightdashClient — configured mode (mocked httpx)
# ===========================================================================

class TestLightdashClientConfigured:
    """Test API calls when LIGHTDASH_URL and LIGHTDASH_API_KEY are set."""

    @pytest.fixture
    def configured_client(self) -> LightdashClient:
        return LightdashClient(
            base_url="http://lightdash.local",
            api_key="test-api-key",
            project_uuid="proj-uuid-123",
        )

    def test_is_available(self, configured_client: LightdashClient) -> None:
        assert configured_client.is_available is True

    def test_embed_url_format(self, configured_client: LightdashClient) -> None:
        url = configured_client.get_dashboard_embed_url("dash-uuid")
        assert url == "http://lightdash.local/projects/proj-uuid-123/dashboards/dash-uuid/view"

    def test_chart_embed_url_format(self, configured_client: LightdashClient) -> None:
        url = configured_client.get_chart_embed_url("chart-uuid")
        assert url == "http://lightdash.local/saved/chart-uuid/view"

    @pytest.mark.asyncio
    async def test_health_check_ok(self, configured_client: LightdashClient) -> None:
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "isAuthenticated": True}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            async with configured_client:
                healthy = await configured_client.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_list_dashboards(self, configured_client: LightdashClient) -> None:
        dashboards = [
            {"uuid": "d1", "name": "Campaign Performance"},
            {"uuid": "d2", "name": "Agent Learning Curve"},
        ]
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": dashboards, "status": "ok"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            async with configured_client:
                result = await configured_client.list_dashboards()
        assert result == dashboards

    @pytest.mark.asyncio
    async def test_run_metric_query(self, configured_client: LightdashClient) -> None:
        rows = [{"campaigns_headline": "Buy Now!", "campaigns_avg_confidence_score": 0.85}]
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": {"rows": rows, "fields": {}}, "status": "ok"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            async with configured_client:
                result = await configured_client.run_metric_query(
                    explore_name="campaigns",
                    dimensions=["campaigns_headline"],
                    metrics=["campaigns_avg_confidence_score"],
                )
        assert result["rows"] == rows

    @pytest.mark.asyncio
    async def test_get_chart_results_on_http_error_returns_empty(
        self, configured_client: LightdashClient
    ) -> None:
        """HTTP errors should be caught and return empty, not raise."""
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            async with configured_client:
                result = await configured_client.get_chart_results("bad-uuid")
        assert result == {"rows": [], "fields": {}}


# ===========================================================================
# lightdash_metrics — SQLite fallback
# ===========================================================================

class TestLightdashMetricsSQLiteFallback:
    """Metrics functions must return data from SQLite when Lightdash is absent."""

    @pytest.mark.asyncio
    async def test_get_campaign_performance_returns_rows(self, tmp_db: Path) -> None:
        rows = await get_campaign_performance(db_path=tmp_db)
        assert len(rows) >= 3
        assert all("headline" in r for r in rows)

    @pytest.mark.asyncio
    async def test_get_campaign_performance_filtered_by_company(self, tmp_db: Path) -> None:
        rows = await get_campaign_performance(company_id="comp1", db_path=tmp_db)
        assert all(r.get("campaign_id") in ("c1", "c2") for r in rows)

    @pytest.mark.asyncio
    async def test_get_agent_learning_curve_returns_aggregates(self, tmp_db: Path) -> None:
        rows = await get_agent_learning_curve(db_path=tmp_db)
        assert len(rows) >= 1
        for row in rows:
            assert "agent_name" in row
            assert "avg_quality_score" in row

    @pytest.mark.asyncio
    async def test_get_agent_learning_curve_filtered_by_agent(self, tmp_db: Path) -> None:
        rows = await get_agent_learning_curve(agent_name="trend_intel", db_path=tmp_db)
        assert all(r["agent_name"] == "trend_intel" for r in rows)

    @pytest.mark.asyncio
    async def test_get_polymarket_calibration_returns_rows(self, tmp_db: Path) -> None:
        rows = await get_polymarket_calibration(db_path=tmp_db)
        assert len(rows) >= 2
        for row in rows:
            assert "signal_category" in row
            assert "accuracy_score" in row

    @pytest.mark.asyncio
    async def test_get_channel_performance_returns_all_channels(self, tmp_db: Path) -> None:
        rows = await get_channel_performance(db_path=tmp_db)
        channels = {r["channel"] for r in rows}
        assert "twitter" in channels
        assert "linkedin" in channels

    @pytest.mark.asyncio
    async def test_get_channel_performance_filtered(self, tmp_db: Path) -> None:
        rows = await get_channel_performance(channel="email", db_path=tmp_db)
        assert all(r["channel"] == "email" for r in rows)

    @pytest.mark.asyncio
    async def test_get_cross_company_patterns_returns_high_confidence(self, tmp_db: Path) -> None:
        rows = await get_cross_company_patterns(min_confidence=0.8, db_path=tmp_db)
        assert all(r["confidence"] >= 0.8 for r in rows)

    @pytest.mark.asyncio
    async def test_get_cross_company_patterns_filter_by_type(self, tmp_db: Path) -> None:
        rows = await get_cross_company_patterns(
            pattern_type="channel", min_confidence=0.0, db_path=tmp_db
        )
        assert all(r["pattern_type"] == "channel" for r in rows)

    @pytest.mark.asyncio
    async def test_get_safety_metrics_aggregates_correctly(self, tmp_db: Path) -> None:
        result = await get_safety_metrics(db_path=tmp_db)
        assert result["total_campaigns"] == 3
        assert result["blocked_count"] == 1
        assert abs(result["block_rate"] - round(1 / 3, 4)) < 0.001
        assert result["passed_count"] == 2

    @pytest.mark.asyncio
    async def test_get_safety_metrics_empty_db_returns_zeros(self) -> None:
        """A missing DB should return the zero-state dict, not raise."""
        result = await get_safety_metrics(db_path=Path("/nonexistent/signal.db"))
        assert result["total_campaigns"] == 0
        assert result["block_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_query_sqlite_nonexistent_db_returns_empty(self) -> None:
        rows = await _query_sqlite("SELECT 1", db_path=Path("/nonexistent/signal.db"))
        assert rows == []


# ===========================================================================
# lightdash_metrics — with mocked LightdashClient (Lightdash available)
# ===========================================================================

class TestLightdashMetricsWithLightdash:
    """When a LightdashClient is available, metric functions should prefer it."""

    def _make_mock_client(self, rows: List[Dict[str, Any]]) -> LightdashClient:
        """Return a LightdashClient whose run_metric_query returns *rows*."""
        client = MagicMock(spec=LightdashClient)
        client.is_available = True
        client.run_metric_query = AsyncMock(return_value={"rows": rows, "fields": {}})
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.mark.asyncio
    async def test_campaign_performance_uses_lightdash_rows(self, tmp_db: Path) -> None:
        ld_rows = [{"campaign_id": "ld1", "headline": "From Lightdash", "engagement_rate": 0.12}]
        client = self._make_mock_client(ld_rows)
        result = await get_campaign_performance(client=client, db_path=tmp_db)
        assert result == ld_rows

    @pytest.mark.asyncio
    async def test_falls_back_to_sqlite_when_lightdash_returns_empty(
        self, tmp_db: Path
    ) -> None:
        """When Lightdash returns no rows, fall back to SQLite."""
        client = self._make_mock_client([])  # empty rows → trigger fallback
        result = await get_campaign_performance(client=client, db_path=tmp_db)
        # SQLite should return 3 campaigns
        assert len(result) >= 3

    @pytest.mark.asyncio
    async def test_agent_learning_curve_uses_lightdash(self, tmp_db: Path) -> None:
        ld_rows = [{"agent_name": "campaign_gen", "day": "2026-02-20", "avg_quality_score": 0.92}]
        client = self._make_mock_client(ld_rows)
        result = await get_agent_learning_curve(client=client, db_path=tmp_db)
        assert result == ld_rows

    @pytest.mark.asyncio
    async def test_cross_company_patterns_uses_lightdash(self, tmp_db: Path) -> None:
        ld_rows = [{"pattern_type": "timing", "confidence": 0.95, "sample_size": 300}]
        client = self._make_mock_client(ld_rows)
        result = await get_cross_company_patterns(client=client, db_path=tmp_db)
        assert result == ld_rows

    @pytest.mark.asyncio
    async def test_safety_metrics_uses_lightdash_row(self, tmp_db: Path) -> None:
        ld_rows = [{"total_campaigns": 100, "blocked_count": 5, "block_rate": 0.05}]
        client = self._make_mock_client(ld_rows)
        result = await get_safety_metrics(client=client, db_path=tmp_db)
        assert result["total_campaigns"] == 100


# ===========================================================================
# get_analytics_embed_urls
# ===========================================================================

class TestAnalyticsEmbedUrls:
    def test_returns_all_panel_keys(self) -> None:
        urls = get_analytics_embed_urls()
        expected_keys = {
            "campaign_performance",
            "agent_learning_curve",
            "polymarket_calibration",
            "channel_performance",
            "cross_company_patterns",
            "safety_metrics",
        }
        assert set(urls.keys()) == expected_keys

    def test_empty_strings_when_not_configured(self) -> None:
        urls = get_analytics_embed_urls()
        # No env vars set → all empty strings
        assert all(v == "" for v in urls.values())

    def test_urls_populated_when_env_set(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LIGHTDASH_URL": "http://lightdash.local",
                "LIGHTDASH_PROJECT_UUID": "proj-123",
                "LIGHTDASH_DASHBOARD_CAMPAIGN_PERF_UUID": "dash-abc",
            },
        ):
            client = LightdashClient()
            urls = get_analytics_embed_urls(client)
        assert "dash-abc" in urls["campaign_performance"]


# ===========================================================================
# FastAPI router
# ===========================================================================

class TestLightdashRouter:
    """Test the FastAPI endpoints using the TestClient."""

    @pytest.fixture
    def app(self):
        from fastapi import FastAPI
        from code.backend.routers.lightdash import router
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def test_client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_status_endpoint_unconfigured(self, test_client) -> None:
        resp = test_client.get("/api/lightdash/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert data["healthy"] is False

    def test_embed_urls_endpoint_returns_all_keys(self, test_client) -> None:
        resp = test_client.get("/api/lightdash/embed-urls")
        assert resp.status_code == 200
        data = resp.json()
        assert "campaign_performance" in data

    def test_campaign_performance_endpoint(self, test_client, tmp_db: Path) -> None:
        with patch(
            "code.backend.integrations.lightdash_metrics.get_campaign_performance",
            new_callable=AsyncMock,
            return_value=[{"campaign_id": "c1", "headline": "Test"}],
        ):
            resp = test_client.get("/api/lightdash/metrics/campaign-performance")
        assert resp.status_code == 200
        assert resp.json()[0]["headline"] == "Test"

    def test_agent_learning_curve_endpoint(self, test_client) -> None:
        with patch(
            "code.backend.integrations.lightdash_metrics.get_agent_learning_curve",
            new_callable=AsyncMock,
            return_value=[{"agent_name": "campaign_gen", "avg_quality_score": 0.9}],
        ):
            resp = test_client.get("/api/lightdash/metrics/agent-learning-curve")
        assert resp.status_code == 200

    def test_webhook_endpoint_accepts_payload(self, test_client) -> None:
        payload = {
            "name": "Low Engagement Alert",
            "savedChartUuid": "chart-123",
            "tag": "loop1_low_engagement",
            "thresholdResult": {"value": 0.02, "threshold": 0.05},
        }
        resp = test_client.post(
            "/api/lightdash/webhooks/threshold-alert",
            json=payload,
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

    def test_webhook_endpoint_handles_unknown_tag(self, test_client) -> None:
        payload = {"name": "Unknown Alert", "tag": "unknown_tag"}
        resp = test_client.post(
            "/api/lightdash/webhooks/threshold-alert",
            json=payload,
        )
        assert resp.status_code == 202

    def test_safety_metrics_endpoint(self, test_client) -> None:
        with patch(
            "code.backend.integrations.lightdash_metrics.get_safety_metrics",
            new_callable=AsyncMock,
            return_value={"total_campaigns": 10, "blocked_count": 1, "block_rate": 0.1},
        ):
            resp = test_client.get("/api/lightdash/metrics/safety")
        assert resp.status_code == 200
        assert resp.json()["block_rate"] == 0.1

    def test_days_param_validation(self, test_client) -> None:
        resp = test_client.get("/api/lightdash/metrics/campaign-performance?days=0")
        assert resp.status_code == 422  # FastAPI validation error

    def test_min_confidence_param_validation(self, test_client) -> None:
        resp = test_client.get(
            "/api/lightdash/metrics/cross-company-patterns?min_confidence=1.5"
        )
        assert resp.status_code == 422


# ===========================================================================
# _days_ago utility
# ===========================================================================

class TestDaysAgo:
    def test_returns_string(self) -> None:
        result = _days_ago(7)
        assert isinstance(result, str)

    def test_earlier_than_now(self) -> None:
        from datetime import datetime
        result = datetime.fromisoformat(_days_ago(7))
        assert result < datetime.utcnow()

    def test_30_days_ago_is_roughly_30_days(self) -> None:
        from datetime import datetime
        result = datetime.fromisoformat(_days_ago(30))
        diff = datetime.utcnow() - result
        assert 29 <= diff.days <= 31
