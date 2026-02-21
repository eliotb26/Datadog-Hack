/**
 * SIGNAL — shared API helper
 *
 * Provides:
 *  - apiFetch(path, options)           — thin wrapper around fetch with base URL + JSON
 *  - submitJob(path, body)             — POST async job, returns { job_id }
 *  - pollJob(jobId, opts)              — polls GET /api/jobs/:id until terminal, returns result
 *  - submitAndPoll(path, body, opts)   — convenience: submit + poll in one call
 */

export const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Fetch helper — adds Content-Type and base URL, throws on non-2xx.
 */
export async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || body.message || detail
    } catch {}
    // Provide clearer messages for common errors
    if (res.status === 500 && !detail) {
      detail = 'Server error. Ensure the backend is running on port 8000.'
    }
    if (res.status === 502 || res.status === 503) {
      detail = 'Backend unreachable. Start the backend with: uvicorn backend.main:app --port 8000'
    }
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json()
}

/**
 * Submit an async job and return { job_id, status }.
 */
export async function submitJob(path, body = {}) {
  return apiFetch(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/**
 * Poll GET /api/jobs/:id until the job reaches a terminal state.
 *
 * @param {string}   jobId
 * @param {object}   opts
 * @param {number}   opts.intervalMs   - polling interval (default 2000 ms)
 * @param {number}   opts.timeoutMs    - max wait before throwing (default 120000 ms)
 * @param {function} opts.onProgress   - called with the JobRecord each poll tick
 * @returns {Promise<any>}             - resolves with job.result on success
 */
export async function pollJob(jobId, opts = {}) {
  const {
    intervalMs = 2000,
    timeoutMs = 120_000,
    onProgress = null,
  } = opts

  const deadline = Date.now() + timeoutMs

  while (Date.now() < deadline) {
    const job = await apiFetch(`/api/jobs/${jobId}`)
    if (onProgress) onProgress(job)
    if (job.status === 'succeeded') return job.result
    if (job.status === 'failed') throw new Error(job.error || 'Job failed')
    await new Promise(r => setTimeout(r, intervalMs))
  }

  throw new Error(`Job ${jobId} timed out after ${timeoutMs / 1000}s`)
}

/**
 * Submit an async job, then poll until complete, and return the result payload.
 */
export async function submitAndPoll(path, body = {}, opts = {}) {
  const { job_id } = await submitJob(path, body)
  return pollJob(job_id, opts)
}
