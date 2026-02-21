"""SIGNAL — In-process async job registry.

Endpoints that trigger agent pipelines (campaign generation, signal refresh, etc.)
are slow (5-60 s).  They submit a job and return 202 + job_id immediately; the
frontend polls GET /api/jobs/{job_id} until status is "succeeded" or "failed".
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
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
    progress_message: Optional[str] = None
    progress_step: Optional[int] = None
    progress_total: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# In-process store — dict key access is thread-safe in CPython
_store: Dict[str, JobRecord] = {}
_MAX_JOBS = 1000
_TERMINAL_TTL = timedelta(hours=24)


def _cleanup_store() -> None:
    now = datetime.utcnow()
    expired: list[str] = []
    for job_id, record in _store.items():
        terminal = record.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}
        if terminal and (now - record.updated_at) > _TERMINAL_TTL:
            expired.append(job_id)
    for job_id in expired:
        _store.pop(job_id, None)

    if len(_store) <= _MAX_JOBS:
        return

    overflow = len(_store) - _MAX_JOBS
    oldest = sorted(_store.values(), key=lambda r: r.updated_at)
    for record in oldest[:overflow]:
        _store.pop(record.job_id, None)


def create_job(job_type: JobType) -> JobRecord:
    """Create and register a new job. Returns the JobRecord."""
    _cleanup_store()
    job = JobRecord(type=job_type)
    _store[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[JobRecord]:
    _cleanup_store()
    return _store.get(job_id)


def _mark(
    job_id: str,
    status: JobStatus,
    result: Any = None,
    error: Optional[str] = None,
    progress_message: Optional[str] = None,
    progress_step: Optional[int] = None,
    progress_total: Optional[int] = None,
) -> None:
    _cleanup_store()
    record = _store.get(job_id)
    if record:
        record.status = status
        record.result = result
        record.error = error
        if progress_message is not None:
            record.progress_message = progress_message
        if progress_step is not None:
            record.progress_step = progress_step
        if progress_total is not None:
            record.progress_total = progress_total
        record.updated_at = datetime.utcnow()


def mark_running(job_id: str) -> None:
    _mark(job_id, JobStatus.RUNNING)


def mark_succeeded(job_id: str, result: Any) -> None:
    _mark(job_id, JobStatus.SUCCEEDED, result=result)


def mark_failed(job_id: str, error: str) -> None:
    _mark(job_id, JobStatus.FAILED, error=error)


def update_progress(
    job_id: str,
    message: str,
    step: Optional[int] = None,
    total: Optional[int] = None,
) -> None:
    """Update progress metadata on a job while it remains in-flight."""
    _mark(
        job_id,
        JobStatus.RUNNING,
        progress_message=message,
        progress_step=step,
        progress_total=total,
    )


async def run_job(job_id: str, coro) -> None:
    """Execute *coro*, updating job state before/after.  Call via asyncio.create_task."""
    mark_running(job_id)
    try:
        result = await coro
        mark_succeeded(job_id, result)
    except Exception as exc:  # noqa: BLE001
        mark_failed(job_id, str(exc))
