"""ElevenLabs Voice Agent — standalone text-to-speech integration.

Converts text to natural speech using ElevenLabs API.
Can save to file or return audio bytes for streaming/playback.

Usage:
    from integrations.elevenlabs_voice import ElevenLabsVoiceClient

    client = ElevenLabsVoiceClient()
    client.text_to_speech("Hello, this is a test.", output_path="output.mp3")
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator, Optional

import structlog

log = structlog.get_logger(__name__)

# Default voice (Rachel - clear, professional)
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


class ElevenLabsVoiceClient:
    """Standalone client for ElevenLabs text-to-speech voice agent."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: str = DEFAULT_VOICE_ID,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.getenv("ELEVENLABS_API_KEY", ""))
        self.voice_id = voice_id
        self.model_id = model_id

    @property
    def is_configured(self) -> bool:
        """True when API key is set and not a placeholder."""
        key = (self.api_key or "").strip()
        return bool(key) and key != "your_elevenlabs_api_key_here"

    def text_to_speech(
        self,
        text: str,
        output_path: Optional[str | Path] = None,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> bytes:
        """Convert text to speech. Returns audio bytes; optionally saves to file.

        Args:
            text: Text to convert to speech.
            output_path: Optional path to save MP3 file.
            voice_id: Override default voice.
            model_id: Override default model.

        Returns:
            Raw audio bytes (MP3).

        Raises:
            ValueError: If API key is not configured.
            Exception: On ElevenLabs API errors.
        """
        if not self.is_configured:
            raise ValueError(
                "ELEVENLABS_API_KEY is not set. Add it to .env (see .env.template)."
            )

        try:
            from elevenlabs.client import ElevenLabs
        except ImportError as e:
            raise ImportError(
                "elevenlabs package is required. Run: pip install elevenlabs"
            ) from e

        client = ElevenLabs(api_key=self.api_key)
        vid = voice_id or self.voice_id
        mid = model_id or self.model_id

        log.info("elevenlabs_tts", text_len=len(text), voice_id=vid, model_id=mid)
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=vid,
            model_id=mid,
            output_format=DEFAULT_OUTPUT_FORMAT,
        )

        # SDK may return bytes or an iterable stream
        if isinstance(audio, bytes):
            data = audio
        elif hasattr(audio, "read"):
            data = audio.read()
        elif hasattr(audio, "__iter__"):
            chunks = list(audio)
            data = b"".join(c if isinstance(c, bytes) else bytes(c) for c in chunks)
        else:
            data = bytes(audio)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            log.info("elevenlabs_tts_saved", path=str(path), size_bytes=len(data))

        return data

    def text_to_speech_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Iterator[bytes]:
        """Stream text-to-speech audio chunks. Yields bytes.

        Useful for real-time playback or streaming responses.
        """
        if not self.is_configured:
            raise ValueError(
                "ELEVENLABS_API_KEY is not set. Add it to .env (see .env.template)."
            )

        try:
            from elevenlabs.client import ElevenLabs
        except ImportError as e:
            raise ImportError(
                "elevenlabs package is required. Run: pip install elevenlabs"
            ) from e

        client = ElevenLabs(api_key=self.api_key)
        vid = voice_id or self.voice_id
        mid = model_id or self.model_id

        stream = client.text_to_speech.stream(
            text=text,
            voice_id=vid,
            model_id=mid,
            output_format=DEFAULT_OUTPUT_FORMAT,
        )

        for chunk in stream:
            if isinstance(chunk, bytes):
                yield chunk
            else:
                yield bytes(chunk)
