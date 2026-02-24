"""
Gemini media helper for image/video generation.

Image: uses generate_content() with response_modalities=["TEXT","IMAGE"]
       on the gemini-2.5-flash-image (or similar) model — returns inline bytes.

Video: uses the async generate_videos() operation on veo-3.1-fast-generate-preview,
       polls until done, then saves video_bytes to disk.

Both functions are intentionally defensive:
- If media generation is disabled or fails they return None.
- Callers keep text-only flow and persist without media URLs.
"""
from __future__ import annotations

import asyncio
import base64
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

from backend.config import settings
from backend.integrations.datadog_metrics import track_api_call

log = structlog.get_logger(__name__)


@dataclass
class MediaAsset:
    asset_url: str
    asset_type: str  # image | video
    provider: str
    model: str


def _media_dir() -> Path:
    base = Path(os.getenv("MEDIA_OUTPUT_DIR", "./data/generated_media"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _write_bytes(data: bytes, suffix: str) -> str:
    file_name = f"{uuid.uuid4().hex}{suffix}"
    out_path = _media_dir() / file_name
    out_path.write_bytes(data)
    # Return a relative URL served by the FastAPI StaticFiles mount at /api/media
    return f"/api/media/{file_name}"


def _extract_inline_image_bytes(response: object) -> Optional[bytes]:
    """
    Extract inline image bytes from a generate_content response.
    Gemini returns image data inside candidates[*].content.parts[*].inline_data.
    The data field is either raw bytes or a base64-encoded string.
    """
    try:
        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is None:
                    continue
                data = getattr(inline_data, "data", None)
                if isinstance(data, (bytes, bytearray)):
                    return bytes(data)
                if isinstance(data, str):
                    return base64.b64decode(data)
    except Exception:
        return None
    return None


async def generate_image_asset(
    prompt: str,
    aspect_ratio: str = "16:9",
    style_hint: str = "",
) -> Optional[MediaAsset]:
    """
    Generate an image with gemini-2.5-flash-image (or GEMINI_IMAGE_MODEL).
    Uses generate_content() with response_modalities=["TEXT", "IMAGE"].
    Saves the returned inline PNG bytes and returns a web-accessible URL.
    """
    if not settings.ENABLE_GEMINI_MEDIA:
        return None
    if not settings.gemini_api_key_set:
        log.warning("gemini_image_generation_skipped", reason="no_api_key")
        return None

    started = time.perf_counter()
    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=settings.llm_api_key)
        full_prompt = prompt if not style_hint else f"{prompt}\nStyle: {style_hint}"

        response = client.models.generate_content(
            model=settings.GEMINI_IMAGE_MODEL,
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        data = _extract_inline_image_bytes(response)
        if data:
            url = _write_bytes(data, ".png")
            track_api_call(
                "gemini_image_gen",
                success=True,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
            log.info("gemini_image_generated", url=url, model=settings.GEMINI_IMAGE_MODEL)
            return MediaAsset(
                asset_url=url,
                asset_type="image",
                provider="gemini",
                model=settings.GEMINI_IMAGE_MODEL,
            )

        # Defensive: some model versions might return an https URL as text
        txt = getattr(response, "text", "") or ""
        txt = txt.strip()
        if txt.startswith("http://") or txt.startswith("https://"):
            track_api_call(
                "gemini_image_gen",
                success=True,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
            return MediaAsset(
                asset_url=txt,
                asset_type="image",
                provider="gemini",
                model=settings.GEMINI_IMAGE_MODEL,
            )

        log.warning(
            "gemini_image_generation_empty",
            model=settings.GEMINI_IMAGE_MODEL,
            response_text=txt[:200],
        )
        track_api_call(
            "gemini_image_gen",
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        return None

    except Exception as exc:  # noqa: BLE001
        track_api_call(
            "gemini_image_gen",
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        log.warning("gemini_image_generation_failed", error=str(exc))
        return None


async def generate_video_asset(
    prompt: str,
    duration_s: int = 8,
    aspect_ratio: str = "16:9",
    style_hint: str = "",
) -> Optional[MediaAsset]:
    """
    Generate a short video with veo-3.1-fast-generate-preview (or GEMINI_VIDEO_MODEL).
    Uses client.models.generate_videos() which returns a long-running operation.
    Polls until done, saves video_bytes to an mp4 file, returns web-accessible URL.
    """
    if not settings.ENABLE_GEMINI_MEDIA or not settings.ENABLE_VIDEO_GEN:
        return None
    if not settings.gemini_api_key_set:
        log.warning("gemini_video_generation_skipped", reason="no_api_key")
        return None

    started = time.perf_counter()
    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=settings.llm_api_key)

        full_prompt = prompt + (f"\nStyle: {style_hint}" if style_hint else "")

        operation = client.models.generate_videos(
            model=settings.GEMINI_VIDEO_MODEL,
            prompt=full_prompt,
            config=genai_types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                number_of_videos=1,
                duration_seconds=min(max(duration_s, 4), 8),  # API supports 4-8s
            ),
        )

        # Poll the operation until it completes (Veo is async by design)
        timeout_s = settings.GEMINI_MEDIA_TIMEOUT_S
        poll_interval = 10  # seconds between polls
        elapsed = 0

        while not operation.done:
            if elapsed >= timeout_s:
                log.warning(
                    "gemini_video_generation_timeout",
                    elapsed_s=elapsed,
                    model=settings.GEMINI_VIDEO_MODEL,
                )
                track_api_call(
                    "gemini_video_gen",
                    success=False,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
                return None
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            operation = client.operations.get(operation)

        if not operation.response or not operation.response.generated_videos:
            log.warning("gemini_video_generation_empty", model=settings.GEMINI_VIDEO_MODEL)
            track_api_call(
                "gemini_video_gen",
                success=False,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
            return None

        video_obj = operation.response.generated_videos[0].video

        # video_bytes is None for remote Veo videos — download via the signed URI.
        # The URI requires the API key in the x-goog-api-key header and follows a redirect.
        video_bytes = getattr(video_obj, "video_bytes", None)

        if not video_bytes:
            uri = getattr(video_obj, "uri", None)
            if uri:
                import httpx
                resp = httpx.get(
                    uri,
                    headers={"x-goog-api-key": settings.llm_api_key},
                    timeout=60,
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    video_bytes = resp.content
                else:
                    log.warning(
                        "gemini_video_download_failed",
                        status=resp.status_code,
                        uri=uri[:80],
                    )

        if video_bytes:
            url = _write_bytes(bytes(video_bytes), ".mp4")
            track_api_call(
                "gemini_video_gen",
                success=True,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
            log.info("gemini_video_generated", url=url, model=settings.GEMINI_VIDEO_MODEL)
            return MediaAsset(
                asset_url=url,
                asset_type="video",
                provider="gemini",
                model=settings.GEMINI_VIDEO_MODEL,
            )

        log.warning(
            "gemini_video_no_bytes",
            model=settings.GEMINI_VIDEO_MODEL,
            video_obj_attrs=str(dir(video_obj))[:300],
        )
        track_api_call(
            "gemini_video_gen",
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        return None

    except Exception as exc:  # noqa: BLE001
        track_api_call(
            "gemini_video_gen",
            success=False,
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        log.warning("gemini_video_generation_failed", error=str(exc))
        return None
