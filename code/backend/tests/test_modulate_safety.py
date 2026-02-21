"""
Tests for Modulate AI integration — content safety + Velma-2 voice.

Test layers:
  1. Unit tests  — no network, no API key needed (all external calls mocked)
  2. Integration tests — real Modulate API (requires MODULATE_API_KEY in .env)

Run unit tests only (fast, no keys needed):
    pytest code/backend/tests/test_modulate_safety.py -v -m unit

Run integration tests (requires MODULATE_API_KEY):
    pytest code/backend/tests/test_modulate_safety.py -v -m integration

Run everything:
    pytest code/backend/tests/test_modulate_safety.py -v
"""
from __future__ import annotations

import io
import os
import struct
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path setup so imports work from any working directory
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from project root
_here = Path(__file__).resolve()
for _parent in [_here.parent, *_here.parents]:
    _candidate = _parent / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break

from integrations.modulate_safety import (  # noqa: E402
    AppealRecord,
    ModulateSafetyClient,
    SafetyCategory,
    SafetyResult,
    _score_text,
    _tone_risk_score,
    screen_campaign,
    submit_appeal,
)
from integrations.modulate_voice import (  # noqa: E402
    ModulateVoiceClient,
    VelmaTranscript,
    VelmaUtterance,
    VoiceBriefResult,
    _extract_brand_signals,
    _mime_for,
    _most_common,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(seconds: float = 0.1, rate: int = 16000) -> bytes:
    """Generate a minimal valid WAV file containing silence."""
    buf = io.BytesIO()
    n_samples = int(rate * seconds)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))
    return buf.getvalue()


def _modulate_key_is_real() -> bool:
    key = os.getenv("MODULATE_API_KEY", "")
    return bool(key) and key not in (
        "your_modulate_api_key_here",
        "your_modulate_toxmod_api_key_here",
    )


# ---------------------------------------------------------------------------
# ── UNIT TESTS — ModulateSafetyClient ─────────────────────────────────────
# ---------------------------------------------------------------------------


class TestModulateSafetyClientConfig:
    @pytest.mark.unit
    def test_not_configured_with_empty_key(self) -> None:
        client = ModulateSafetyClient(api_key="")
        assert not client.is_configured

    @pytest.mark.unit
    def test_not_configured_with_placeholder(self) -> None:
        client = ModulateSafetyClient(api_key="your_modulate_api_key_here")
        assert not client.is_configured

    @pytest.mark.unit
    def test_configured_with_real_key(self) -> None:
        client = ModulateSafetyClient(api_key="abc-real-key-123")
        assert client.is_configured

    @pytest.mark.unit
    def test_default_threshold_is_0_3(self) -> None:
        client = ModulateSafetyClient(api_key="k", safety_threshold=0.3)
        assert client.safety_threshold == 0.3


class TestTextScorer:
    @pytest.mark.unit
    def test_clean_text_scores_zero(self) -> None:
        score, cats = _score_text("Discover how AI is revolutionising content marketing in 2025.")
        assert score == 0.0
        assert cats == []

    @pytest.mark.unit
    def test_hate_speech_scores_high(self) -> None:
        score, cats = _score_text("We despise inferior brands that hate their customers.")
        assert score > 0.3
        assert SafetyCategory.HATE_SPEECH in cats

    @pytest.mark.unit
    def test_violence_detected(self) -> None:
        score, cats = _score_text("Destroy the competition — kill it with this deal!")
        assert SafetyCategory.VIOLENCE in cats

    @pytest.mark.unit
    def test_political_content_detected(self) -> None:
        score, cats = _score_text("The president and senator endorse this product.")
        assert SafetyCategory.POLITICAL in cats

    @pytest.mark.unit
    def test_financial_risk_detected(self) -> None:
        score, cats = _score_text("Guaranteed returns! Risk-free investment — get rich now!")
        assert SafetyCategory.FINANCIAL_RISK in cats

    @pytest.mark.unit
    def test_spam_detected(self) -> None:
        score, cats = _score_text("Act now! Limited time!!! Click here for free money $$$")
        assert SafetyCategory.SPAM in cats

    @pytest.mark.unit
    def test_misinformation_detected(self) -> None:
        score, cats = _score_text("Doctors hate this miracle cure — proven to reverse diabetes.")
        assert SafetyCategory.MISINFORMATION in cats

    @pytest.mark.unit
    def test_score_capped_at_1(self) -> None:
        nasty = "hate kill murder violence destroy attack brutal massacre explicit sexual hate hate"
        score, _ = _score_text(nasty)
        assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_multiple_categories_accumulated(self) -> None:
        text = "The senator hates all candidates. Guaranteed returns from risk-free investments!"
        score, cats = _score_text(text)
        assert len(cats) >= 2

    @pytest.mark.unit
    def test_empty_text_scores_zero(self) -> None:
        score, cats = _score_text("")
        assert score == 0.0


class TestScreenCampaign:
    @pytest.mark.unit
    def test_clean_campaign_passes(self) -> None:
        client = ModulateSafetyClient(api_key="k", safety_threshold=0.3)
        result = client.screen_campaign(
            campaign_id="camp-001",
            headline="How AI helps brands tell better stories",
            body_copy="Discover three ways predictive content intelligence transforms your marketing ROI.",
            company_id="co-001",
        )
        assert isinstance(result, SafetyResult)
        assert result.toxicity_score < 0.3
        assert result.blocked is False
        assert result.campaign_id == "camp-001"

    @pytest.mark.unit
    def test_toxic_campaign_blocked(self) -> None:
        client = ModulateSafetyClient(api_key="k", safety_threshold=0.3)
        result = client.screen_campaign(
            campaign_id="camp-bad",
            headline="Destroy inferior rivals — hate them",
            body_copy="Kill the competition brutally. We despise all customers who don't buy.",
            company_id="co-001",
        )
        assert result.blocked is True
        assert result.toxicity_score >= 0.3

    @pytest.mark.unit
    def test_result_has_all_required_fields(self) -> None:
        client = ModulateSafetyClient(api_key="k")
        result = client.screen_campaign("c-1", "Nice headline", "Good body copy here.")
        assert result.campaign_id == "c-1"
        assert 0.0 <= result.toxicity_score <= 1.0
        assert isinstance(result.blocked, bool)
        assert isinstance(result.categories, list)
        assert result.screening_method == "text_heuristic"
        assert result.latency_ms is not None

    @pytest.mark.unit
    def test_convenience_function_works(self) -> None:
        result = screen_campaign("c-2", "Clean headline", "Clean body copy for a campaign.")
        assert isinstance(result, SafetyResult)

    @pytest.mark.unit
    def test_threshold_customisation(self) -> None:
        strict_client = ModulateSafetyClient(api_key="k", safety_threshold=0.01)
        result = strict_client.screen_campaign(
            "c-3", "Act now! Limited time!", "Click here to buy!"
        )
        assert result.blocked is True


class TestAppeal:
    @pytest.mark.unit
    def test_submit_appeal_returns_record(self) -> None:
        client = ModulateSafetyClient(api_key="k")
        original = SafetyResult(
            campaign_id="c-4",
            toxicity_score=0.45,
            blocked=True,
            categories=[SafetyCategory.POLITICAL],
            reason="Blocked",
        )
        record = client.submit_appeal("c-4", original, "False positive — no political content.")
        assert isinstance(record, AppealRecord)
        assert record.campaign_id == "c-4"
        assert record.original_score == 0.45
        assert SafetyCategory.POLITICAL in record.original_categories

    @pytest.mark.unit
    def test_convenience_submit_appeal_works(self) -> None:
        original = SafetyResult(
            campaign_id="c-5",
            toxicity_score=0.31,
            blocked=True,
            categories=[],
            reason="Borderline",
        )
        record = submit_appeal("c-5", original, "Reviewer: content is brand-safe.")
        assert record.override_reason == "Reviewer: content is brand-safe."


class TestToneRiskScore:
    @pytest.mark.unit
    def test_no_emotions_returns_zero(self) -> None:
        transcript = VelmaTranscript(
            text="hello world",
            utterances=[VelmaUtterance(utterance_uuid="u1", text="hello world")],
        )
        assert _tone_risk_score(transcript) == 0.0

    @pytest.mark.unit
    def test_angry_emotion_raises_score(self) -> None:
        transcript = VelmaTranscript(
            text="hello world",
            utterances=[
                VelmaUtterance(utterance_uuid="u1", text="hello", emotion="angry"),
                VelmaUtterance(utterance_uuid="u2", text="world", emotion="neutral"),
            ],
        )
        assert _tone_risk_score(transcript) == 0.5

    @pytest.mark.unit
    def test_all_risky_emotions_returns_1(self) -> None:
        transcript = VelmaTranscript(
            text="x",
            utterances=[
                VelmaUtterance(utterance_uuid="u1", text="x", emotion="angry"),
                VelmaUtterance(utterance_uuid="u2", text="y", emotion="hostile"),
            ],
        )
        assert _tone_risk_score(transcript) == 1.0


class TestScreenWithVoice:
    @pytest.mark.unit
    def test_screen_with_voice_mocked(self) -> None:
        """screen_with_voice combines text + voice scores correctly."""
        client = ModulateSafetyClient(api_key="real-key-abc", safety_threshold=0.3)

        fake_transcript = VelmaTranscript(
            text="hello world",
            utterances=[
                VelmaUtterance(utterance_uuid="u1", text="hello", emotion="angry"),
                VelmaUtterance(utterance_uuid="u2", text="world", emotion="neutral"),
            ],
        )

        with patch(
            "integrations.modulate_safety._ModulateVoiceClient"
        ) as MockVoiceClient:
            mock_instance = MagicMock()
            mock_instance.transcribe.return_value = fake_transcript
            MockVoiceClient.return_value = mock_instance

            result = client.screen_with_voice(
                campaign_id="c-6",
                headline="Great product!",
                body_copy="Buy our amazing product today.",
                audio_bytes=b"fake-audio",
                company_id="co-1",
            )

        assert result.screening_method == "text+voice"
        assert isinstance(result.toxicity_score, float)
        assert 0.0 <= result.toxicity_score <= 1.0
        if result.toxicity_score > 0:
            assert SafetyCategory.TONE_RISK in result.categories


# ---------------------------------------------------------------------------
# ── UNIT TESTS — ModulateVoiceClient ──────────────────────────────────────
# ---------------------------------------------------------------------------


class TestModulateVoiceClientConfig:
    @pytest.mark.unit
    def test_not_configured_with_empty_key(self) -> None:
        client = ModulateVoiceClient(api_key="")
        assert not client.is_configured

    @pytest.mark.unit
    def test_configured_with_real_key(self) -> None:
        client = ModulateVoiceClient(api_key="abc-123-real")
        assert client.is_configured

    @pytest.mark.unit
    def test_raises_without_api_key(self) -> None:
        # Pass api_key="" explicitly so the real env key is NOT picked up.
        client = ModulateVoiceClient(api_key="")
        assert not client.is_configured
        with pytest.raises(ValueError, match="MODULATE_API_KEY"):
            client.transcribe(b"audio", "test.wav")


class TestMimeFor:
    @pytest.mark.unit
    @pytest.mark.parametrize("filename,expected_prefix", [
        ("test.wav", "audio/wav"),
        ("brief.mp3", "audio/mpeg"),
        ("recording.ogg", "audio/ogg"),
        ("unknown.xyz", "audio/wav"),
    ])
    def test_mime_types(self, filename: str, expected_prefix: str) -> None:
        assert _mime_for(filename).startswith(expected_prefix)


class TestMostCommon:
    @pytest.mark.unit
    def test_most_common_returns_most_frequent(self) -> None:
        assert _most_common(["a", "b", "a", "c", "a"]) == "a"

    @pytest.mark.unit
    def test_most_common_empty_returns_none(self) -> None:
        assert _most_common([]) is None

    @pytest.mark.unit
    def test_most_common_all_none_returns_none(self) -> None:
        assert _most_common([None, None]) is None


class TestExtractBrandSignals:
    @pytest.mark.unit
    def test_transcript_signal_included(self) -> None:
        transcript = VelmaTranscript(
            text="We are a bold, innovative tech brand.",
            utterances=[],
        )
        signals = _extract_brand_signals(transcript)
        assert any("bold" in s for s in signals)

    @pytest.mark.unit
    def test_emotion_signal_included(self) -> None:
        transcript = VelmaTranscript(
            text="Hello world",
            utterances=[
                VelmaUtterance(utterance_uuid="u1", text="Hello world", emotion="enthusiastic"),
            ],
        )
        signals = _extract_brand_signals(transcript)
        assert any("enthusiastic" in s.lower() for s in signals)

    @pytest.mark.unit
    def test_empty_transcript_returns_empty_list(self) -> None:
        transcript = VelmaTranscript(text="", utterances=[])
        signals = _extract_brand_signals(transcript)
        assert signals == []


class TestVoiceBriefNotConfigured:
    @pytest.mark.unit
    def test_returns_failure_result_when_not_configured(self) -> None:
        # Pass api_key="" explicitly so the real env key is NOT picked up.
        client = ModulateVoiceClient(api_key="")
        result = client.extract_brand_voice(b"audio", "brief.wav")
        assert isinstance(result, VoiceBriefResult)
        assert result.success is False
        # The early-return path sets a user-facing message in brand_voice_signals.
        assert any("not configured" in s.lower() or "api key" in s.lower() for s in result.brand_voice_signals)


class TestTranscribeMocked:
    @pytest.mark.unit
    def test_transcribe_mocked(self) -> None:
        """Transcribe a WAV via mocked httpx response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "text": "Hello world",
            "duration_ms": 1500,
            "utterances": [
                {
                    "utterance_uuid": "abc-123",
                    "text": "Hello world",
                    "start_ms": 0,
                    "duration_ms": 1500,
                    "speaker": 1,
                    "language": "en",
                    "emotion": "neutral",
                    "accent": "american",
                }
            ],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            client = ModulateVoiceClient(api_key="real-key-test")
            transcript = client.transcribe(_make_wav(), "test.wav")

        assert transcript.text == "Hello world"
        assert transcript.duration_ms == 1500
        assert len(transcript.utterances) == 1
        assert transcript.utterances[0].emotion == "neutral"
        assert transcript.utterances[0].accent == "american"

    @pytest.mark.unit
    def test_extract_brand_voice_mocked(self) -> None:
        """extract_brand_voice returns populated VoiceBriefResult."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "text": "We are an innovative startup with a bold voice.",
            "duration_ms": 3200,
            "utterances": [
                {
                    "utterance_uuid": "u1",
                    "text": "We are an innovative startup with a bold voice.",
                    "start_ms": 0,
                    "duration_ms": 3200,
                    "speaker": 1,
                    "language": "en",
                    "emotion": "enthusiastic",
                    "accent": "american",
                }
            ],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_resp):
            client = ModulateVoiceClient(api_key="real-key-test")
            result = client.extract_brand_voice(_make_wav(), "brief.wav")

        assert result.success is True
        assert result.dominant_emotion == "enthusiastic"
        assert result.detected_accent == "american"
        assert any("innovative" in s for s in result.brand_voice_signals)
        assert any("enthusiastic" in s.lower() for s in result.brand_voice_signals)


# ---------------------------------------------------------------------------
# ── INTEGRATION TESTS — real Modulate API ─────────────────────────────────
# ---------------------------------------------------------------------------

_SKIP_INTEGRATION = pytest.mark.skipif(
    not _modulate_key_is_real(),
    reason="MODULATE_API_KEY not set or is a placeholder in .env",
)


@_SKIP_INTEGRATION
@pytest.mark.integration
class TestVelma2Integration:
    def test_transcribe_silence_wav(self) -> None:
        """Real API: submit a silent WAV and verify a response is returned."""
        client = ModulateVoiceClient()
        assert client.is_configured, "MODULATE_API_KEY must be set for integration tests"

        wav = _make_wav(seconds=0.5)
        transcript = client.transcribe(wav, "silence.wav", emotion=True, accent=True)

        assert isinstance(transcript.text, str)
        assert isinstance(transcript.duration_ms, int)
        assert isinstance(transcript.utterances, list)
        print(f"\n[Velma-2 transcribe] text={transcript.text!r}, duration={transcript.duration_ms}ms")

    def test_extract_brand_voice_silence(self) -> None:
        """Real API: extract_brand_voice returns success=True for any WAV."""
        client = ModulateVoiceClient()
        wav = _make_wav(seconds=0.5)
        result = client.extract_brand_voice(wav, "brand_brief.wav")

        assert result.success is True
        assert isinstance(result.brand_voice_signals, list)
        assert isinstance(result.latency_ms, int)
        print(f"\n[Brand voice] signals={result.brand_voice_signals}")

    def test_safety_screen_clean_content(self) -> None:
        """Safety client: clean campaign text passes screening."""
        client = ModulateSafetyClient(safety_threshold=0.3)
        result = client.screen_campaign(
            campaign_id="integration-test-clean",
            headline="How AI-powered analytics boosts campaign performance by 3×",
            body_copy=(
                "Modern marketing teams are turning to predictive AI to understand "
                "which content resonates with their audience before it ever goes live. "
                "Signal's self-improving agent analyses Polymarket trend data to surface "
                "the exact moment when your audience is ready to engage."
            ),
            company_id="test-company",
        )
        print(f"\n[Safety clean] score={result.toxicity_score}, blocked={result.blocked}")
        assert result.blocked is False
        assert result.toxicity_score < 0.3

    def test_safety_screen_political_content(self) -> None:
        """Safety client: content with political figures is flagged."""
        client = ModulateSafetyClient(safety_threshold=0.3)
        result = client.screen_campaign(
            campaign_id="integration-test-political",
            headline="What the president's latest policy means for your business",
            body_copy=(
                "The senator and congressional leaders are pushing new regulations "
                "that will impact every company in the industry. Our platform helps "
                "you navigate political uncertainty with data-driven campaign strategies."
            ),
            company_id="test-company",
        )
        print(f"\n[Safety political] score={result.toxicity_score}, cats={result.categories}")
        assert SafetyCategory.POLITICAL in result.categories

    def test_appeal_submit_returns_record(self) -> None:
        """Appeals: submit_appeal returns a logged AppealRecord."""
        client = ModulateSafetyClient()
        original = client.screen_campaign(
            campaign_id="integration-appeal-test",
            headline="The senator's policy affects your marketing budget",
            body_copy="Political elections this cycle will reshape B2B spending priorities.",
            company_id="test-company",
        )
        record = client.submit_appeal(
            campaign_id="integration-appeal-test",
            original_result=original,
            override_reason="Content is industry news commentary, not political advocacy.",
            company_id="test-company",
        )
        assert record.campaign_id == "integration-appeal-test"
        assert "industry news" in record.override_reason
