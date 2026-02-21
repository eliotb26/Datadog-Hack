# API Design

This document is the comprehensive API reference for the FastAPI backend in
`code/backend/main.py` and all mounted routers.

## Runtime and Docs

- Base URL: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- API version: `0.2.0` (from `FastAPI(... version="0.2.0")`)

## Conventions

- Authentication: no auth middleware is currently enforced in API routes.
- Content type: JSON for request and response bodies unless noted.
- Async jobs: long-running pipelines return `202` with a `job_id`.
- Timestamp format: ISO-8601 strings.
- Path prefixes:
  - `/api/company`
  - `/api/signals`
  - `/api/campaigns`
  - `/api/content`
  - `/api/feedback`
  - `/api/jobs`
- Static media:
  - generated assets are served at `/api/media/*`
  - physical directory defaults to `./data/generated_media` or `MEDIA_OUTPUT_DIR`.

## Async Job Lifecycle

`POST` endpoints that trigger agent workflows enqueue jobs and return quickly.
Poll `GET /api/jobs/{job_id}` until terminal status.

Job states:

1. `queued`
2. `running`
3. `succeeded` or `failed`

Job types:

- `signal_refresh`
- `campaign_generate`
- `content_strategy_generate`
- `content_piece_generate`
- `feedback_trigger`

Example job record:

```json
{
  "job_id": "d4f7c3e1-9d6b-4b6a-b6b9-3396b2b20c2f",
  "type": "campaign_generate",
  "status": "succeeded",
  "result": {},
  "error": null,
  "created_at": "2026-02-21T10:00:00.000000",
  "updated_at": "2026-02-21T10:01:30.000000"
}
```

## Endpoint Catalog

### System

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Service metadata |
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/jobs/{job_id}` | Poll async job state |
| `GET` | `/api/media/{path}` | Serve generated media files |

### Company

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/company/intake` | Create/update profile via Brand Intake Agent |
| `GET` | `/api/company/profile` | Get latest company profile |
| `GET` | `/api/company/profile/{company_id}` | Get company profile by ID |
| `POST` | `/api/company/fetch-website` | Fetch/extract website text preview |

### Signals

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/signals` | List persisted trend signals |
| `GET` | `/api/signals/{signal_id}` | Get one trend signal |
| `POST` | `/api/signals/refresh` | Async Agent 2 refresh + persist |

### Campaigns

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/campaigns/generate` | Async Agent 2 (optional) + 3 + 4 |
| `GET` | `/api/campaigns` | List campaigns |
| `GET` | `/api/campaigns/{campaign_id}` | Campaign detail + metrics |
| `POST` | `/api/campaigns/{campaign_id}/approve` | Mark campaign approved |
| `POST` | `/api/campaigns/{campaign_id}/metrics` | Record campaign performance metrics |

### Content

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/content/strategies/generate` | Async Agent 6 strategy generation |
| `GET` | `/api/content/strategies` | List content strategies |
| `GET` | `/api/content/strategies/{strategy_id}` | Strategy detail |
| `POST` | `/api/content/pieces/generate` | Async Agent 7 content generation |
| `GET` | `/api/content/pieces` | List content pieces |
| `GET` | `/api/content/pieces/{piece_id}` | Content piece detail |
| `PATCH` | `/api/content/pieces/{piece_id}/status` | Update piece workflow status |

### Feedback

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/feedback/trigger` | Async Agent 5 feedback loops |

### Lightdash (Optional Router)

`code/backend/routers/lightdash.py` exists but is not mounted by default in
`code/backend/main.py`. To expose these routes, include the lightdash router.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/lightdash/status` | Lightdash configuration and health |
| `GET` | `/api/lightdash/embed-urls` | Dashboard embed URLs |
| `GET` | `/api/lightdash/metrics/campaign-performance` | Campaign metrics |
| `GET` | `/api/lightdash/metrics/agent-learning-curve` | Agent quality trends |
| `GET` | `/api/lightdash/metrics/polymarket-calibration` | Signal calibration |
| `GET` | `/api/lightdash/metrics/channel-performance` | Channel performance |
| `GET` | `/api/lightdash/metrics/cross-company-patterns` | Pattern insights |
| `GET` | `/api/lightdash/metrics/safety` | Safety metrics |
| `POST` | `/api/lightdash/webhooks/threshold-alert` | Threshold alert receiver |

## Detailed Contracts

### `GET /`

- Response `200`:

```json
{
  "service": "SIGNAL",
  "version": "0.2.0",
  "docs": "/docs"
}
```

### `GET /health`

- Response `200`:

```json
{ "status": "ok" }
```

### `GET /api/jobs/{job_id}`

- Path param:
  - `job_id` string
- Response `200`: `JobRecord`
- Response `404`: job not found

---

### `POST /api/company/intake`

Create/update profile from structured form fields and optional website context.

Request body:

- Required:
  - `companyName` string (min length 1)
  - `industry` string (min length 1)
- Optional:
  - `website` string or null
  - `description` string or null
  - `audience` string or null
  - `tone` string or null
  - `goals` string or null
  - `avoidTopics` string or null
  - `competitors` string[]
  - `content_history` string[]
  - `visual_style` string

Response `200`:

- `success` boolean
- `company_id` string or null
- `agent_response` string or null
- `latency_ms` integer or null
- `message` string or null

Possible errors:

- `422` invalid payload
- `500` intake pipeline error

### `GET /api/company/profile`

- Response `200`: latest company profile
- Response `404`: no profile found

Profile shape:

```json
{
  "id": "company-uuid",
  "name": "Acme",
  "industry": "SaaS",
  "website": "https://acme.com",
  "tone_of_voice": "Professional",
  "target_audience": "B2B marketers",
  "campaign_goals": "Thought leadership",
  "competitors": ["X", "Y"],
  "content_history": ["..."],
  "visual_style": "Minimal",
  "safety_threshold": 0.7
}
```

### `GET /api/company/profile/{company_id}`

- Path param:
  - `company_id` string
- Response `200`: same shape as latest profile
- Response `404`: company not found

### `POST /api/company/fetch-website`

Request:

```json
{ "url": "https://example.com" }
```

Response `200`:

```json
{
  "success": true,
  "text": "Extracted text...",
  "message": null
}
```

If extraction fails, route still returns `200` with `success: false`.
`422` when `url` is missing.

---

### `GET /api/signals`

Query params:

- `category` optional string
- `limit` optional integer, default `50`, max `200`

Response `200`: array of signal objects.

Signal object:

```json
{
  "id": "signal-uuid",
  "polymarket_market_id": "market-id",
  "title": "Will X happen by Y?",
  "category": "macro",
  "probability": 0.64,
  "probability_pct": 64.0,
  "probability_momentum": 0.12,
  "volume": 150000.0,
  "volume_velocity": 0.33,
  "relevance_scores": { "company-uuid": 0.88 },
  "surfaced_at": "2026-02-21T10:00:00.000000",
  "expires_at": null
}
```

### `GET /api/signals/{signal_id}`

- Path param:
  - `signal_id` string
- Response `200`: one signal
- Response `404`: signal not found

### `POST /api/signals/refresh`

Starts Agent 2 and persists returned signals.

Request:

```json
{
  "company_id": "company-uuid",
  "top_n": 5
}
```

Notes:

- `company_id` optional; backend falls back to latest profile.
- `top_n` default is `5`.

Response `202`:

```json
{
  "job_id": "job-uuid",
  "status": "queued"
}
```

Job `result` on success:

```json
{
  "signals_surfaced": 5,
  "signals": []
}
```

---

### `POST /api/campaigns/generate`

Runs campaign pipeline:

1. load company profile
2. load provided signals or run Agent 2
3. run Agent 3 generation
4. run Agent 4 routing

Request:

```json
{
  "company_id": "company-uuid",
  "signal_ids": ["signal-uuid-1", "signal-uuid-2"],
  "n_concepts": 3
}
```

Validation:

- `n_concepts` min `1`, max `5`, default `3`

Response `202`:

```json
{
  "job_id": "job-uuid",
  "status": "queued"
}
```

Successful job `result`:

```json
{
  "company_id": "company-uuid",
  "campaigns": [],
  "distribution_plans": [],
  "signals_used": []
}
```

### `GET /api/campaigns`

Query params:

- `company_id` optional string
- `status` optional string
- `limit` optional integer, default `50`, max `200`

Response `200`: array of campaigns.

Campaign item shape:

```json
{
  "id": "campaign-uuid",
  "company_id": "company-uuid",
  "trend_signal_id": "signal-uuid",
  "headline": "Headline",
  "body_copy": "Body",
  "visual_direction": "Visual guidance",
  "visual_asset_url": "/api/media/file.png",
  "confidence_score": 0.86,
  "channel_recommendation": "linkedin",
  "channel_reasoning": "Reasoning text",
  "safety_score": 0.1,
  "safety_passed": true,
  "status": "draft",
  "created_at": "2026-02-21T10:10:00.000000"
}
```

### `GET /api/campaigns/{campaign_id}`

- Path param:
  - `campaign_id` string
- Response `200`: campaign object plus `metrics` array
- Response `404`: campaign not found

### `POST /api/campaigns/{campaign_id}/approve`

- Path param:
  - `campaign_id` string
- Response `200`:

```json
{
  "campaign_id": "campaign-uuid",
  "status": "approved"
}
```

- Response `404`: campaign not found

### `POST /api/campaigns/{campaign_id}/metrics`

Request:

```json
{
  "channel": "linkedin",
  "impressions": 5000,
  "clicks": 250,
  "engagement_rate": 0.05,
  "sentiment_score": 0.78
}
```

Fields:

- `channel` required string
- `impressions` optional int, default `0`
- `clicks` optional int, default `0`
- `engagement_rate` optional float, default `0.0`
- `sentiment_score` optional float or null

Response `200`:

```json
{
  "metric_id": "metric-uuid",
  "campaign_id": "campaign-uuid",
  "status": "recorded"
}
```

---

### `POST /api/content/strategies/generate`

Starts Agent 6 to generate content strategies from a campaign.

Request:

```json
{ "campaign_id": "campaign-uuid" }
```

Response `202`:

```json
{ "job_id": "job-uuid", "status": "queued" }
```

Job success result:

```json
{
  "campaign_id": "campaign-uuid",
  "strategies": [],
  "success": true
}
```

### `GET /api/content/strategies`

Query params:

- `campaign_id` optional string
- `company_id` optional string

Response `200`: array of strategy objects.

Strategy object:

```json
{
  "id": "strategy-uuid",
  "campaign_id": "campaign-uuid",
  "company_id": "company-uuid",
  "content_type": "linkedin_article",
  "reasoning": "Why this format",
  "target_length": "800-1200 words",
  "tone_direction": "Authoritative, practical",
  "structure_outline": ["Hook", "Data", "CTA"],
  "priority_score": 0.84,
  "visual_needed": false,
  "created_at": "2026-02-21T10:20:00.000000"
}
```

### `GET /api/content/strategies/{strategy_id}`

- Path param:
  - `strategy_id` string
- Response `200`: strategy object
- Response `404`: strategy not found

### `POST /api/content/pieces/generate`

Starts Agent 7 to generate content pieces from one strategy.

Request:

```json
{ "strategy_id": "strategy-uuid" }
```

Response `202`:

```json
{ "job_id": "job-uuid", "status": "queued" }
```

Job success result:

```json
{
  "strategy_id": "strategy-uuid",
  "pieces": [],
  "success": true
}
```

### `GET /api/content/pieces`

Query params:

- `strategy_id` optional string
- `campaign_id` optional string
- `company_id` optional string

Response `200`: array of content pieces.

Piece object:

```json
{
  "id": "piece-uuid",
  "strategy_id": "strategy-uuid",
  "campaign_id": "campaign-uuid",
  "company_id": "company-uuid",
  "content_type": "linkedin_article",
  "title": "Title",
  "body": "Content body",
  "summary": "Summary",
  "word_count": 850,
  "visual_prompt": null,
  "visual_asset_url": null,
  "quality_score": 0.9,
  "brand_alignment": 0.88,
  "status": "draft",
  "created_at": "2026-02-21T10:25:00.000000"
}
```

### `GET /api/content/pieces/{piece_id}`

- Path param:
  - `piece_id` string
- Response `200`: piece object
- Response `404`: piece not found

### `PATCH /api/content/pieces/{piece_id}/status`

Request:

```json
{ "status": "review" }
```

Allowed statuses:

- `draft`
- `review`
- `approved`
- `published`

Response `200`:

```json
{
  "piece_id": "piece-uuid",
  "status": "review"
}
```

Errors:

- `422` invalid status value or missing field
- `404` piece not found

---

### `POST /api/feedback/trigger`

Starts Agent 5 loops.

Request:

```json
{
  "company_id": "company-uuid",
  "run_loop1": true,
  "run_loop2": true,
  "run_loop3": true
}
```

Defaults:

- `company_id`: `null`
- `run_loop1`: `true`
- `run_loop2`: `true`
- `run_loop3`: `true`

Response `202`:

```json
{ "job_id": "job-uuid", "status": "queued" }
```

Job success result is `FeedbackLoopResult`, including:

- `run_id`
- `loop1`, `loop2`, `loop3` result objects
- `overall_summary`
- `success`
- `total_latency_ms`
- `executed_at`

## Common Error Responses

- `404` resource not found, for example:
  - profile missing
  - campaign/signal/strategy/piece ID not found
  - unknown job ID
- `405` method not allowed on valid path
- `422` request validation error (missing/invalid fields or query bounds)
- `500` internal pipeline failure (agent/integration exceptions)

## Workflow Playbooks

### 1. Onboard Company

1. `POST /api/company/intake`
2. `GET /api/company/profile`

### 2. Refresh Trend Signals

1. `POST /api/signals/refresh`
2. Poll `GET /api/jobs/{job_id}`
3. `GET /api/signals`

### 3. Generate and Approve Campaign

1. `POST /api/campaigns/generate`
2. Poll `GET /api/jobs/{job_id}`
3. `GET /api/campaigns`
4. `POST /api/campaigns/{campaign_id}/approve`

### 4. Produce Content

1. `POST /api/content/strategies/generate`
2. Poll `GET /api/jobs/{job_id}`
3. `GET /api/content/strategies`
4. `POST /api/content/pieces/generate`
5. Poll `GET /api/jobs/{job_id}`
6. `PATCH /api/content/pieces/{piece_id}/status`

### 5. Trigger Feedback Loops

1. `POST /api/feedback/trigger`
2. Poll `GET /api/jobs/{job_id}`

## Frontend Integration Pattern

The frontend uses these helpers in `code/frontend/src/lib/api.js`:

- `apiFetch(path, options)`
- `submitJob(path, body)`
- `pollJob(jobId, opts)`
- `submitAndPoll(path, body, opts)`

Example:

```js
const { job_id } = await submitJob("/api/campaigns/generate", { company_id, n_concepts: 3 })
const result = await pollJob(job_id, { intervalMs: 2000, timeoutMs: 120000 })
```

## Notes

- Source of truth for exact schemas is always `/openapi.json`.
- This document reflects current router behavior in the repository code.

---

**Prev**: [Data Model](./04-data-model.md) | **Next**: [Frontend Architecture](./06-frontend-architecture.md) | [Full Index](../ARCHITECTURE.md)
