"""Job status router — GET /api/jobs/{job_id}

Frontend submits async agent jobs (campaign generation, signal refresh, etc.)
and polls this endpoint until the job reaches a terminal state.
"""
from fastapi import APIRouter, HTTPException
from backend.jobs import get_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job_status(job_id: str):
    """Return the current state of an async job.

    Terminal states:  succeeded | failed
    In-progress:      queued | running

    On success the ``result`` field contains the job output payload.
    On failure the ``error`` field contains a short description.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job.model_dump(mode="json")
