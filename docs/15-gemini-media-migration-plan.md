# Gemini Media Migration Plan

## Documentation Critique

1. Provider consistency was broken:
- Multiple docs referenced Flora for visuals while the codebase and architecture center on Gemini.
- This created ambiguity around API keys, ownership, and demo narrative.

2. Sponsor framing was inconsistent:
- Flora was listed as a separate dependency, but media generation is now part of the DeepMind/Gemini path.
- Some docs still implied 8/8 sponsor utilization even after this shift.

3. Implementation detail depth was uneven:
- Agent-level docs mentioned visual generation, but lacked concrete image/video execution details.
- Infra docs mixed provider-specific env vars that no longer match desired architecture.

4. Project structure doc is partially stale:
- It references paths like `backend/` and `frontend/`, while active code lives under `code/backend` and `code/frontend`.
- Integration module naming (`flora_visuals.py`) no longer matches planned provider.

## Codebase Change Plan

## Goal
Replace Flora-based visual generation with Gemini image/video generation in Agent 3 and Agent 7 flows, without breaking existing campaign/content APIs.

## Phase 1 - Configuration and Contracts

1. Update settings in `code/backend/config.py`:
- Remove `FLORA_API_KEY` usage.
- Add Gemini media config fields:
  - `GEMINI_IMAGE_MODEL` (default `gemini-2.5-flash-image`)
  - `GEMINI_VIDEO_MODEL` (project-approved default)
  - `GEMINI_MEDIA_TIMEOUT_S`

2. Update integration module contracts:
- Create/rename integration client to `code/backend/integrations/gemini_media.py`.
- Define stable methods:
  - `generate_image(prompt, aspect_ratio, style_hint)`
  - `generate_video(prompt, duration_s, aspect_ratio, style_hint)`
- Keep return payload normalized: `asset_url`, `asset_type`, `provider`, `model`, `metadata`.

## Phase 2 - Agent Pipeline Integration

1. Update Agent 3 in `code/backend/agents/campaign_gen.py`:
- Replace Flora prompt assumptions with Gemini media prompt strategy.
- Generate image (and optional video concept URL) per campaign concept.
- Persist generated URL into `campaigns.visual_asset_url`.

2. Update Agent 7 in `code/backend/agents/content_production.py`:
- Replace "Flora prompt" wording with Gemini media prompt.
- For `video_script`, request a draft video asset when `visual_needed` is true.
- Preserve graceful fallback when media generation fails.

3. Update model descriptions:
- `code/backend/models/campaign.py`
- `code/backend/models/content.py`
- Replace Flora-specific field descriptions with Gemini/provider-neutral descriptions.

## Phase 3 - API, UI, and Observability

1. API routes:
- Validate response serialization still includes `visual_prompt` and `visual_asset_url` in:
  - `code/backend/routers/campaigns.py`
  - `code/backend/routers/content.py`

2. Frontend:
- Update media labels and badges in:
  - `code/frontend/src/pages/Campaigns.jsx`
  - `code/frontend/src/pages/Generate.jsx`
  - `code/frontend/src/pages/ContentStudio.jsx`
- If `asset_type=video`, show video preview player fallback to thumbnail.

3. Observability:
- Track Gemini media call success/latency/error tags in:
  - `code/backend/integrations/datadog_metrics.py`
- Suggested tags: `provider:gemini`, `modality:image|video`, `status:ok|error`.

## Phase 4 - Tests and Validation

1. Unit tests:
- Add coverage for media client wrapper in `code/backend/tests/`.
- Add campaign/content tests for image/video URL population.

2. Integration tests:
- Extend existing ADK integration tests to assert media generation fallback behavior.
- Ensure no hard dependency on live media APIs in CI (mock required).

3. Acceptance checklist:
- Campaign generation returns at least one valid visual URL when enabled.
- Video-script content can optionally return video asset URL.
- Datadog metrics show media API success/error counts.

## Rollout Strategy

1. Behind a feature flag:
- `ENABLE_GEMINI_MEDIA=true`
- `ENABLE_VIDEO_GEN=false` initially, then enabled after smoke tests.

2. Backward compatibility:
- Keep `visual_asset_url` schema unchanged for now.
- Keep old rows readable without migration.

3. Failure mode:
- On media generation error, return text content with `visual_asset_url=null` and log warning.

---

**Prev**: [Demo Script](./14-demo-script.md) | [Full Index](../ARCHITECTURE.md)
