"""
SIGNAL — Modulate Velma-2 Voice Integration

Processes company voice briefs using Modulate's Velma-2 STT API.
Extracts brand voice signals (tone, emotion, accent) that feed into the
Campaign Generation Agent for better brand-aligned content.

Two main use cases:
  1. Voice Brief Input:   Company records a brief; Velma-2 transcribes + analyses it;
                          brand voice signals are injected into the campaign agent.
  2. Tone Screening:      Audio content (from TTS) can be screened for emotional tone risk.

API:     https://modulate-prototype-apis.com/api/velma-2-stt-batch
Auth:    X-API-Key header (get key from Carter: carterhuffman8385 on hackathon Discord)
Docs:    README from hackathon_docs.zip (Velma-2 OpenAPI .yaml)

Usage:
    from backend.integrations.modulate_voice import ModulateVoiceClient

    client = ModulateVoiceClient()
    result = client.extract_brand_voice(audio_bytes, "brief.wav")
    # result.brand_voice_signals → list of strings for Campaign Gen Agent system prompt
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import List, Optional

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger(__name__)

_VELMA_BASE_URL = "https://modulate-prototype-apis.com"
_BATCH_ENDPOINT = "/api/velma-2-stt-batch"
_VFAST_ENDPOINT = "/api/velma-2-stt-batch-english-vfast"

_PLACEHOLDER_KEYS = {
    "your_modulate_api_key_here",
    "your_modulate_toxmod_api_key_here",
}


# ---------------------------------------------------------------------------
# Response models — match Velma-2 JSON schema exactly
# ---------------------------------------------------------------------------


class VelmaUtterance(BaseModel):
    """A single utterance returned by Velma-2."""

    utterance_uuid: str
    text: str
    start_ms: int = 0
    duration_ms: int = 0
    speaker: int = 1
    language: Optional[str] = None
    emotion: Optional[str] = None
    accent: Optional[str] = None


class VelmaTranscript(BaseModel):
    """Full transcript response from the Velma-2 batch STT endpoint."""

    text: str
    duration_ms: int = 0
    utterances: List[VelmaUtterance] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Brand voice result (what SIGNAL stores and injects into Campaign Agent)
# ---------------------------------------------------------------------------


class VoiceBriefResult(BaseModel):
    """
    Processed result of a company voice brief.

    `brand_voice_signals` is a list of human-readable strings describing
    detected tone, emotion, accent, and brand style — injected directly
    into the Campaign Generation Agent's system prompt.
    """

    transcript: str = ""
    dominant_emotion: Optional[str] = None
    detected_accent: Optional[str] = None
    language: Optional[str] = None
    brand_voice_signals: List[str] = Field(default_factory=list)
    duration_ms: int = 0
    latency_ms: Optional[int] = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ModulateVoiceClient:
    """
    Client for Modulate's Velma-2 voice transcription + understanding API.

    Gracefully falls back (returns empty result) when MODULATE_API_KEY is not set.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        # Use the passed key exactly if given; fall back to env only when key is None.
        self.api_key = (
            os.getenv("MODULATE_API_KEY", "") if api_key is None else api_key
        ).strip()
        self._base_url = os.getenv("MODULATE_VELMA_BASE_URL", _VELMA_BASE_URL).rstrip("/")

    @property
    def is_configured(self) -> bool:
        """True when a real (non-placeholder) API key is set."""
        return bool(self.api_key) and self.api_key not in _PLACEHOLDER_KEYS

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        *,
        emotion: bool = True,
        accent: bool = True,
        diarization: bool = False,
    ) -> VelmaTranscript:
        """
        Transcribe audio using the Velma-2 batch STT endpoint.

        Args:
            audio_bytes:  Raw audio file bytes (WAV or MP3 recommended).
            filename:     Filename hint — used to infer MIME type.
            emotion:      Enable per-utterance emotion detection.
            accent:       Enable per-utterance accent detection.
            diarization:  Enable speaker diarization.

        Returns:
            VelmaTranscript with full transcript text and per-utterance data.

        Raises:
            ValueError:         If API key is not configured.
            ImportError:        If httpx is not installed.
            httpx.HTTPError:    On API-level error (non-2xx response).
        """
        if not self.is_configured:
            raise ValueError(
                "MODULATE_API_KEY is not configured. "
                "Get the API key from Carter on the hackathon Discord (#modulate-ai)."
            )

        try:
            import httpx
        except ImportError as exc:
            raise ImportError("httpx is required: pip install httpx") from exc

        mime = _mime_for(filename)
        endpoint = f"{self._base_url}{_BATCH_ENDPOINT}"

        log.info(
            "velma_transcribe_start",
            filename=filename,
            size_bytes=len(audio_bytes),
            emotion=emotion,
            accent=accent,
        )
        t0 = time.perf_counter()

        response = httpx.post(
            endpoint,
            headers={"X-API-Key": self.api_key},
            files={"upload_file": (filename, audio_bytes, mime)},
            data={
                "emotion": str(emotion).lower(),
                "accent": str(accent).lower(),
                "diarization": str(diarization).lower(),
            },
            timeout=120,
        )

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            log.error(
                "velma_transcribe_error",
                status=response.status_code,
                body=response.text[:500],
                latency_ms=elapsed_ms,
            )
            raise

        data = response.json()
        transcript = VelmaTranscript(**data)

        log.info(
            "velma_transcribe_ok",
            chars=len(transcript.text),
            utterances=len(transcript.utterances),
            duration_ms=transcript.duration_ms,
            latency_ms=elapsed_ms,
        )
        return transcript

    def extract_brand_voice(
        self,
        audio_bytes: bytes,
        filename: str = "voice_brief.wav",
    ) -> VoiceBriefResult:
        """
        Process a company voice brief and extract brand voice signals.

        The result's `brand_voice_signals` list contains human-readable strings
        describing the detected brand tone, emotion, and accent — designed to be
        appended to the Campaign Generation Agent's system prompt so it writes
        content that matches how the company actually sounds.

        Args:
            audio_bytes:  The audio recording of the company's voice brief.
            filename:     Filename of the recording.

        Returns:
            VoiceBriefResult — always returns (never raises); success=False on error.
        """
        if not self.is_configured:
            log.warning(
                "modulate_voice_skipped",
                reason="MODULATE_API_KEY not set",
            )
            return VoiceBriefResult(
                success=False,
                error="MODULATE_API_KEY not configured",
                brand_voice_signals=["No voice brief processed — Modulate API key not configured."],
            )

        t0 = time.perf_counter()
        try:
            transcript = self.transcribe(
                audio_bytes, filename, emotion=True, accent=True, diarization=False
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            log.error("modulate_brand_voice_failed", error=str(exc), latency_ms=elapsed_ms)
            return VoiceBriefResult(success=False, error=str(exc))

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        signals = _extract_brand_signals(transcript)
        dominant_emotion = _most_common(
            [u.emotion for u in transcript.utterances if u.emotion]
        )
        detected_accent = _most_common(
            [u.accent for u in transcript.utterances if u.accent]
        )
        language = _most_common(
            [u.language for u in transcript.utterances if u.language]
        )

        log.info(
            "modulate_brand_voice_ok",
            emotion=dominant_emotion,
            accent=detected_accent,
            language=language,
            signals=len(signals),
            latency_ms=elapsed_ms,
        )

        return VoiceBriefResult(
            transcript=transcript.text,
            dominant_emotion=dominant_emotion,
            detected_accent=detected_accent,
            language=language,
            brand_voice_signals=signals,
            duration_ms=transcript.duration_ms,
            latency_ms=elapsed_ms,
            success=True,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _mime_for(filename: str) -> str:
    """Return an appropriate MIME type based on the audio file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
    return {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "ogg": "audio/ogg",
        "opus": "audio/ogg; codecs=opus",
        "flac": "audio/flac",
        "webm": "audio/webm",
    }.get(ext, "audio/wav")


def _most_common(items: list) -> Optional[str]:
    """Return the most frequently occurring non-None value in a list."""
    filtered = [x for x in items if x is not None]
    if not filtered:
        return None
    return max(set(filtered), key=filtered.count)


def _extract_brand_signals(transcript: VelmaTranscript) -> List[str]:
    """
    Convert a VelmaTranscript into actionable brand voice signal strings
    ready for injection into the Campaign Generation Agent system prompt.
    """
    signals: List[str] = []

    text = (transcript.text or "").strip()
    if text:
        preview = text[:300] + ("..." if len(text) > 300 else "")
        signals.append(f'Voice brief says: "{preview}"')

    emotions = [u.emotion for u in transcript.utterances if u.emotion]
    if emotions:
        dominant = _most_common(emotions)
        signals.append(
            f"Brand tone detected by voice AI: {dominant} "
            f"— write campaign copy that matches this emotional register."
        )

    accents = [u.accent for u in transcript.utterances if u.accent]
    if accents:
        dominant_accent = _most_common(accents)
        signals.append(
            f"Speaker accent / market context: {dominant_accent} "
            f"— adapt cultural references appropriately."
        )

    langs = [u.language for u in transcript.utterances if u.language]
    if langs:
        lang = _most_common(langs)
        if lang and lang.lower() not in ("en", "en-us", "en-gb"):
            signals.append(f"Voice brief is in: {lang} — consider localisation.")

    if transcript.duration_ms > 0:
        secs = transcript.duration_ms / 1000
        signals.append(f"Voice brief duration: {secs:.1f}s")

    return signals


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_client: Optional[ModulateVoiceClient] = None


def get_voice_client() -> ModulateVoiceClient:
    """Return the shared ModulateVoiceClient instance (lazy-init)."""
    global _default_client
    if _default_client is None:
        _default_client = ModulateVoiceClient()
    return _default_client
