"""Background scheduler for automatic Agent 5 feedback loop runs."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import backend.database as db_module
from backend.agents.feedback_loop import run_feedback_loop
from backend.config import settings

log = logging.getLogger(__name__)


class FeedbackScheduler:
    """Periodic scheduler that triggers Agent 5 after enough new campaigns."""

    def __init__(
        self,
        interval_s: int,
        campaigns_per_cycle: int,
        run_loop1: bool,
        run_loop2: bool,
        run_loop3: bool,
        run_on_start: bool = False,
    ) -> None:
        self.interval_s = max(30, int(interval_s))
        self.campaigns_per_cycle = max(1, int(campaigns_per_cycle))
        self.run_loop1 = bool(run_loop1)
        self.run_loop2 = bool(run_loop2)
        self.run_loop3 = bool(run_loop3)
        self.run_on_start = bool(run_on_start)
        self._task: Optional[asyncio.Task] = None
        self._last_campaign_count: int = 0

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._last_campaign_count = await db_module.count_campaigns()
        self._task = asyncio.create_task(self._run_forever(), name="feedback-scheduler")
        log.info(
            "feedback_scheduler_started interval_s=%s campaigns_per_cycle=%s run_loop1=%s run_loop2=%s run_loop3=%s run_on_start=%s",
            self.interval_s,
            self.campaigns_per_cycle,
            self.run_loop1,
            self.run_loop2,
            self.run_loop3,
            self.run_on_start,
        )

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if not task:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        log.info("feedback_scheduler_stopped")

    async def _run_forever(self) -> None:
        if self.run_on_start:
            await self._tick()
        while True:
            await asyncio.sleep(self.interval_s)
            await self._tick()

    async def _tick(self) -> None:
        try:
            current_count = await db_module.count_campaigns()
            delta = current_count - self._last_campaign_count
            if delta < self.campaigns_per_cycle:
                log.info(
                    "feedback_scheduler_skip campaigns_since_last=%s campaigns_required=%s",
                    delta,
                    self.campaigns_per_cycle,
                )
                return

            company_id = None
            if self.run_loop1:
                row = await db_module.get_latest_company_row()
                company_id = row["id"] if row else None
                if not company_id:
                    log.warning("feedback_scheduler_skip_no_company_for_loop1")
                    return

            result = await run_feedback_loop(
                company_id=company_id,
                run_loop1=self.run_loop1,
                run_loop2=self.run_loop2,
                run_loop3=self.run_loop3,
            )
            self._last_campaign_count = current_count
            log.info(
                "feedback_scheduler_triggered campaigns_since_last=%s company_id=%s success=%s",
                delta,
                company_id,
                bool(getattr(result, "success", False)),
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("feedback_scheduler_tick_failed: %s", exc)


def create_feedback_scheduler() -> Optional[FeedbackScheduler]:
    """Build scheduler from env config, or return None when disabled."""
    if not settings.FEEDBACK_SCHEDULER_ENABLED:
        log.info("feedback_scheduler_disabled")
        return None

    if not settings.gemini_api_key_set:
        log.warning("feedback_scheduler_disabled_no_gemini_key")
        return None

    return FeedbackScheduler(
        interval_s=settings.FEEDBACK_SCHEDULER_INTERVAL_S,
        campaigns_per_cycle=settings.CAMPAIGNS_PER_CYCLE,
        run_loop1=settings.FEEDBACK_SCHEDULER_RUN_LOOP1,
        run_loop2=settings.FEEDBACK_SCHEDULER_RUN_LOOP2,
        run_loop3=settings.FEEDBACK_SCHEDULER_RUN_LOOP3,
        run_on_start=settings.FEEDBACK_SCHEDULER_RUN_ON_START,
    )
