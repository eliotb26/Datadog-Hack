from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.feedback_scheduler import FeedbackScheduler, create_feedback_scheduler


@pytest.mark.asyncio
async def test_tick_triggers_feedback_when_campaign_threshold_met():
    scheduler = FeedbackScheduler(
        interval_s=60,
        campaigns_per_cycle=2,
        run_loop1=False,
        run_loop2=True,
        run_loop3=True,
    )
    scheduler._last_campaign_count = 1

    with patch("backend.feedback_scheduler.db_module.count_campaigns", AsyncMock(return_value=4)), patch(
        "backend.feedback_scheduler.run_feedback_loop",
        AsyncMock(return_value=type("R", (), {"success": True})()),
    ) as run_mock:
        await scheduler._tick()

    run_mock.assert_awaited_once()
    kwargs = run_mock.await_args.kwargs
    assert kwargs["run_loop1"] is False
    assert kwargs["run_loop2"] is True
    assert kwargs["run_loop3"] is True
    assert scheduler._last_campaign_count == 4


@pytest.mark.asyncio
async def test_tick_skips_when_threshold_not_met():
    scheduler = FeedbackScheduler(
        interval_s=60,
        campaigns_per_cycle=3,
        run_loop1=False,
        run_loop2=True,
        run_loop3=True,
    )
    scheduler._last_campaign_count = 10

    with patch("backend.feedback_scheduler.db_module.count_campaigns", AsyncMock(return_value=12)), patch(
        "backend.feedback_scheduler.run_feedback_loop",
        AsyncMock(),
    ) as run_mock:
        await scheduler._tick()

    run_mock.assert_not_called()
    assert scheduler._last_campaign_count == 10


@pytest.mark.asyncio
async def test_tick_skips_loop1_when_no_company():
    scheduler = FeedbackScheduler(
        interval_s=60,
        campaigns_per_cycle=1,
        run_loop1=True,
        run_loop2=False,
        run_loop3=False,
    )
    scheduler._last_campaign_count = 0

    with patch("backend.feedback_scheduler.db_module.count_campaigns", AsyncMock(return_value=2)), patch(
        "backend.feedback_scheduler.db_module.get_latest_company_row",
        AsyncMock(return_value=None),
    ), patch("backend.feedback_scheduler.run_feedback_loop", AsyncMock()) as run_mock:
        await scheduler._tick()

    run_mock.assert_not_called()
    assert scheduler._last_campaign_count == 0


def test_create_feedback_scheduler_disabled_when_no_key(monkeypatch):
    monkeypatch.setattr("backend.feedback_scheduler.settings.FEEDBACK_SCHEDULER_ENABLED", True)
    monkeypatch.setattr("backend.feedback_scheduler.settings.GEMINI_API_KEY", "")
    scheduler = create_feedback_scheduler()
    assert scheduler is None

