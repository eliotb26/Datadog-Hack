"""Tests for ElevenLabs Voice Agent integration.

Test layers:
  1. Unit tests — no network, no API key required (mocked)
  2. Integration tests — real ElevenLabs API (requires ELEVENLABS_API_KEY in .env)

Run all:
    pytest code/backend/tests/test_elevenlabs.py -v

Run only unit tests (no API key needed):
    pytest code/backend/tests/test_elevenlabs.py -v -m unit

Run integration tests (needs ELEVENLABS_API_KEY in .env):
    pytest code/backend/tests/test_elevenlabs.py -v -m integration
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from project root (walk up from tests/)
_here = Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from integrations.elevenlabs_voice import (
    DEFAULT_MODEL_ID,
    DEFAULT_VOICE_ID,
    ElevenLabsVoiceClient,
)


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests (no network, mocked)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_client_is_configured_with_valid_key() -> None:
    """Client reports configured when API key is set."""
    client = ElevenLabsVoiceClient(api_key="sk-valid-key-123")
    assert client.is_configured is True


@pytest.mark.unit
def test_client_not_configured_with_empty_key() -> None:
    """Client reports not configured when API key is empty."""
    client = ElevenLabsVoiceClient(api_key="")
    assert client.is_configured is False


@pytest.mark.unit
def test_client_not_configured_with_placeholder() -> None:
    """Client reports not configured when API key is placeholder."""
    client = ElevenLabsVoiceClient(api_key="your_elevenlabs_api_key_here")
    assert client.is_configured is False


@pytest.mark.unit
def test_text_to_speech_raises_without_api_key() -> None:
    """text_to_speech raises ValueError when API key is not set."""
    client = ElevenLabsVoiceClient(api_key="")
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        client.text_to_speech("Hello")


@pytest.mark.unit
def test_text_to_speech_mocked(tmp_path: Path) -> None:
    """text_to_speech returns and saves audio when API is mocked."""
    fake_audio = b"\xff\xfb\x90\x00"  # minimal MP3-like bytes
    mock_convert = MagicMock(return_value=fake_audio)

    with patch("elevenlabs.client.ElevenLabs") as mock_eleven:
        mock_client = MagicMock()
        mock_client.text_to_speech.convert = mock_convert
        mock_eleven.return_value = mock_client

        client = ElevenLabsVoiceClient(api_key="sk-test")
        output_file = tmp_path / "test_output.mp3"

        result = client.text_to_speech(
            "Hello, this is a test.",
            output_path=str(output_file),
        )

        assert result == fake_audio
        assert output_file.exists()
        assert output_file.read_bytes() == fake_audio
        mock_convert.assert_called_once()
        call_kw = mock_convert.call_args.kwargs
        assert call_kw["text"] == "Hello, this is a test."
        assert call_kw["voice_id"] == DEFAULT_VOICE_ID
        assert call_kw["model_id"] == DEFAULT_MODEL_ID


@pytest.mark.unit
def test_text_to_speech_stream_raises_without_api_key() -> None:
    """text_to_speech_stream raises ValueError when API key is not set."""
    client = ElevenLabsVoiceClient(api_key="")
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        list(client.text_to_speech_stream("Hello"))


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests (real API, requires ELEVENLABS_API_KEY)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ELEVENLABS_API_KEY") or os.getenv("ELEVENLABS_API_KEY") == "your_elevenlabs_api_key_here",
    reason="ELEVENLABS_API_KEY not set in .env",
)
def test_text_to_speech_integration(tmp_path: Path) -> None:
    """Real API: convert text to speech and save to file."""
    client = ElevenLabsVoiceClient()
    assert client.is_configured

    output_file = tmp_path / "elevenlabs_test.mp3"
    result = client.text_to_speech(
        "Hello. This is a test of the ElevenLabs voice agent.",
        output_path=str(output_file),
    )

    assert len(result) > 100
    assert output_file.exists()
    assert output_file.stat().st_size == len(result)
    # MP3 files start with ID3 or 0xFF 0xFB
    assert result[:2] == b"\xff\xfb" or result[:3] == b"ID3"
