"""Feedback router — /api/feedback

POST /api/feedback/trigger   — async job: run Agent 5 (Feedback Loop meta-agent)
                               Executes Loop 1 (per-company prompt weights),
                               Loop 2 (cross-company patterns), Loop 3 (signal calibration)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.jobs import JobType, create_job, run_job

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackTriggerRequest(BaseModel):
    company_id: Optional[str] = None
    run_loop1: bool = True
    run_loop2: bool = True
    run_loop3: bool = True


async def _feedback_worker(
    company_id: Optional[str],
    run_loop1: bool,
    run_loop2: bool,
    run_loop3: bool,
) -> dict:
    from backend.agents.feedback_loop import run_feedback_loop

    result = await run_feedback_loop(
        company_id=company_id,
        run_loop1=run_loop1,
        run_loop2=run_loop2,
        run_loop3=run_loop3,
    )
    return result.model_dump(mode="json")


@router.post("/trigger", status_code=202)
async def trigger_feedback(req: FeedbackTriggerRequest):
    """Submit async job to run the Agent 5 feedback loop.

    - Loop 1: updates per-company prompt weights based on campaign performance
    - Loop 2: discovers cross-company style/timing patterns
    - Loop 3: recalibrates Polymarket signal relevance weights

    Returns job_id — poll GET /api/jobs/{job_id} for completion.
    """
    job = create_job(JobType.FEEDBACK_TRIGGER)
    asyncio.create_task(
        run_job(
            job.job_id,
            _feedback_worker(req.company_id, req.run_loop1, req.run_loop2, req.run_loop3),
        )
    )
    return {"job_id": job.job_id, "status": job.status}
