"""SIGNAL — In-process async job registry.

Endpoints that trigger agent pipelines (campaign generation, signal refresh, etc.)
are slow (5-60 s).  They submit a job and return 202 + job_id immediately; the
frontend polls GET /api/jobs/{job_id} until status is "succeeded" or "failed".
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobType(str, Enum):
    SIGNAL_REFRESH = "signal_refresh"
    CAMPAIGN_GENERATE = "campaign_generate"
    CONTENT_STRATEGY_GENERATE = "content_strategy_generate"
    CONTENT_PIECE_GENERATE = "content_piece_generate"
    FEEDBACK_TRIGGER = "feedback_trigger"


class JobRecord(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: JobType
    status: JobStatus = JobStatus.QUEUED
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# In-process store — dict key access is thread-safe in CPython
_store: Dict[str, JobRecord] = {}


def create_job(job_type: JobType) -> JobRecord:
    """Create and register a new job. Returns the JobRecord."""
    job = JobRecord(type=job_type)
    _store[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[JobRecord]:
    return _store.get(job_id)


def _mark(
    job_id: str,
    status: JobStatus,
    result: Any = None,
    error: Optional[str] = None,
) -> None:
    record = _store.get(job_id)
    if record:
        record.status = status
        record.result = result
        record.error = error
        record.updated_at = datetime.utcnow()


def mark_running(job_id: str) -> None:
    _mark(job_id, JobStatus.RUNNING)


def mark_succeeded(job_id: str, result: Any) -> None:
    _mark(job_id, JobStatus.SUCCEEDED, result=result)


def mark_failed(job_id: str, error: str) -> None:
    _mark(job_id, JobStatus.FAILED, error=error)


async def run_job(job_id: str, coro) -> None:
    """Execute *coro*, updating job state before/after.  Call via asyncio.create_task."""
    mark_running(job_id)
    try:
        result = await coro
        mark_succeeded(job_id, result)
    except Exception as exc:  # noqa: BLE001
        mark_failed(job_id, str(exc))
