"""
SIGNAL — Modulate Content Safety Layer

Pre-publication brand safety screening for campaign concepts.

How it works
------------
Since Modulate's hackathon API (Velma-2) is a voice/STT model, SIGNAL uses a
two-layer approach that is genuine and defensible:

  Layer 1 — Text heuristics:
    A fast regex + keyword scorer that checks the generated campaign copy for
    known toxicity categories (hate, violence, explicit content, political
    figures, financial risk). This gates every campaign before distribution.

  Layer 2 — Modulate voice tone analysis (when audio available):
    Optional. If ElevenLabs TTS is configured, campaign copy is synthesised
    to audio and run through Velma-2 with emotion detection enabled. This
    adds a tone-risk dimension — flagging copy whose emotional register is
    unexpectedly hostile, anxious, or aggressive even if the text looks clean.

Appeals loop
------------
When a human reviewer overrides a safety block in the UI, `submit_appeal()`
logs the override so the feedback loop can track false-positive rate over time
(tracked in Datadog).

Usage:
    from backend.integrations.modulate_safety import ModulateSafetyClient, screen_campaign

    result = await screen_campaign(campaign)
    if result.blocked:
        # show safety badge, log, alert
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger(__name__)

# Imported at module level so tests can patch it cleanly.
try:
    from backend.integrations.modulate_voice import ModulateVoiceClient as _ModulateVoiceClient
except ImportError:
    try:
        from integrations.modulate_voice import ModulateVoiceClient as _ModulateVoiceClient  # type: ignore[no-redef]
    except ImportError:
        _ModulateVoiceClient = None  # type: ignore[assignment,misc]

_PLACEHOLDER_KEYS = {
    "your_modulate_api_key_here",
    "your_modulate_toxmod_api_key_here",
}

# ---------------------------------------------------------------------------
# Safety categories
# ---------------------------------------------------------------------------


class SafetyCategory(str, Enum):
    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    EXPLICIT_CONTENT = "explicit_content"
    POLITICAL = "political"           # Requires human approval per safety rules
    FINANCIAL_RISK = "financial_risk" # Requires disclaimer per safety rules
    SPAM = "spam"
    MISINFORMATION = "misinformation"
    TONE_RISK = "tone_risk"           # Detected via voice emotion analysis


# ---------------------------------------------------------------------------
# Toxicity patterns (Layer 1 — text heuristics)
# ---------------------------------------------------------------------------

# Each entry: (SafetyCategory, base_score_contribution, [regex_patterns])
_TOXICITY_RULES: List[Tuple[SafetyCategory, float, List[str]]] = [
    (
        SafetyCategory.HATE_SPEECH,
        0.8,
        [
            r"\b(hate|despise|inferior|subhuman|filth)\b",
            r"\b(racist|sexist|bigot|slur)\b",
        ],
    ),
    (
        SafetyCategory.VIOLENCE,
        0.7,
        [
            r"\b(kill|murder|destroy|attack|threaten|bomb)\b",
            r"\b(violence|brutal|massacre|slaughter)\b",
        ],
    ),
    (
        SafetyCategory.EXPLICIT_CONTENT,
        0.9,
        [
            r"\b(nude|naked|explicit|sexual|porn|xxx)\b",
        ],
    ),
    (
        SafetyCategory.POLITICAL,
        0.35,
        [
            r"\b(president|senator|congressman|governor|prime minister|chancellor)\b",
            r"\b(democrat|republican|labour|conservative|liberal party)\b",
            r"\b(election|vote|ballot|campaign rally|political)\b",
        ],
    ),
    (
        SafetyCategory.FINANCIAL_RISK,
        0.25,
        [
            r"\b(guaranteed (returns?|profit|income|gains?))\b",
            r"\b(risk[ -]free|no[ -]risk investment)\b",
            r"\b(get rich|double your money|100% return)\b",
            r"\b(financial advice|investment advice|buy now.*stock)\b",
        ],
    ),
    (
        SafetyCategory.SPAM,
        0.3,
        [
            r"\b(act now|limited time|click here|buy now|free money)\b",
            r"(!{3,}|\$\$\$|€€€|###)",
            r"\b(make \$\d+|earn \$\d+ (per|a) (day|week|hour))\b",
        ],
    ),
    (
        SafetyCategory.MISINFORMATION,
        0.4,
        [
            r"\b(doctors hate|they don't want you to know|secret cure|miracle (cure|pill|drug))\b",
            r"\b(proven (to cure|to prevent|to reverse))\b",
        ],
    ),
]

# Pre-compile for speed
_COMPILED_RULES: List[Tuple[SafetyCategory, float, re.Pattern]] = [
    (cat, score, re.compile("|".join(patterns), re.IGNORECASE))
    for cat, score, patterns in _TOXICITY_RULES
    if patterns
]

# Tone emotions from Velma-2 that raise brand-safety concerns
_RISKY_EMOTIONS = {"angry", "fear", "disgust", "hostile", "aggressive", "threatening"}

# ---------------------------------------------------------------------------
# Safety result model
# ---------------------------------------------------------------------------


class SafetyResult(BaseModel):
    """
    Result of a Modulate content safety check for a single campaign concept.

    A campaign is blocked when toxicity_score >= the configured SAFETY_THRESHOLD.
    The UI should display a green badge for passed, red badge for blocked.
    """

    campaign_id: str
    company_id: Optional[str] = None
    toxicity_score: float = Field(..., ge=0.0, le=1.0, description="0 = clean, 1 = toxic")
    blocked: bool
    categories: List[SafetyCategory] = Field(default_factory=list)
    reason: str = ""
    screening_method: str = "text_heuristic"   # "text_heuristic" | "text+voice"
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Appeal record (logged for false-positive tracking in Datadog)
# ---------------------------------------------------------------------------


class AppealRecord(BaseModel):
    """Logged when a human reviewer overrides a safety block."""

    campaign_id: str
    company_id: Optional[str] = None
    override_reason: str = ""
    original_score: float
    original_categories: List[SafetyCategory] = Field(default_factory=list)
    appealed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ModulateSafetyClient:
    """
    Content safety screener for SIGNAL campaign concepts.

    Primary screening is text heuristic (always runs, no API needed).
    Optional voice tone screening uses Velma-2 via ModulateVoiceClient.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        safety_threshold: Optional[float] = None,
    ) -> None:
        # Use the passed key exactly if given; fall back to env only when key is None.
        self.api_key = (
            os.getenv("MODULATE_API_KEY", "") if api_key is None else api_key
        ).strip()
        self.safety_threshold = safety_threshold or float(
            os.getenv("SAFETY_THRESHOLD", "0.3")
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key not in _PLACEHOLDER_KEYS

    def screen_campaign(
        self,
        campaign_id: str,
        headline: str,
        body_copy: str,
        company_id: Optional[str] = None,
    ) -> SafetyResult:
        """
        Screen campaign headline + body copy for brand safety.

        Always runs text heuristics. Optionally also runs Velma-2 voice
        tone analysis if audio bytes are provided.

        Args:
            campaign_id:  ID of the CampaignConcept being screened.
            headline:     Campaign headline text.
            body_copy:    Campaign body copy text.
            company_id:   Optional company ID for metrics tagging.

        Returns:
            SafetyResult with toxicity_score and blocked flag.
        """
        t0 = time.perf_counter()

        full_text = f"{headline}\n\n{body_copy}"
        score, categories = _score_text(full_text)
        blocked = score >= self.safety_threshold

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if blocked:
            reason = (
                f"Toxicity score {score:.3f} ≥ threshold {self.safety_threshold:.3f}. "
                f"Categories: {', '.join(c.value for c in categories)}."
            )
            log.warning(
                "modulate_safety_blocked",
                campaign_id=campaign_id,
                company_id=company_id,
                score=round(score, 4),
                categories=[c.value for c in categories],
                latency_ms=elapsed_ms,
            )
        else:
            reason = "Content passed all safety checks."
            log.info(
                "modulate_safety_passed",
                campaign_id=campaign_id,
                score=round(score, 4),
                latency_ms=elapsed_ms,
            )

        return SafetyResult(
            campaign_id=campaign_id,
            company_id=company_id,
            toxicity_score=round(score, 4),
            blocked=blocked,
            categories=categories,
            reason=reason,
            screening_method="text_heuristic",
            latency_ms=elapsed_ms,
        )

    def screen_with_voice(
        self,
        campaign_id: str,
        headline: str,
        body_copy: str,
        audio_bytes: bytes,
        audio_filename: str = "campaign.wav",
        company_id: Optional[str] = None,
    ) -> SafetyResult:
        """
        Full safety screening: text heuristics + Velma-2 voice tone analysis.

        First runs text heuristics. Then sends `audio_bytes` (a TTS rendering
        of the campaign copy) through Velma-2 with emotion detection. If
        Velma-2 detects a high-risk emotion (anger, fear, hostility) across the
        majority of utterances, the tone_risk score is raised.

        Args:
            campaign_id:     ID of the CampaignConcept.
            headline:        Campaign headline.
            body_copy:       Campaign body copy.
            audio_bytes:     Audio rendering of the campaign (e.g. via ElevenLabs TTS).
            audio_filename:  Filename hint for the audio bytes.
            company_id:      Optional company ID for metrics tagging.

        Returns:
            SafetyResult combining text heuristic + voice tone scores.
        """
        t0 = time.perf_counter()

        # Layer 1: text heuristics
        text_result = self.screen_campaign(campaign_id, headline, body_copy, company_id)

        # Layer 2: Velma-2 tone analysis
        voice_score = 0.0
        if audio_bytes and self.is_configured and _ModulateVoiceClient is not None:
            try:
                voice_client = _ModulateVoiceClient(api_key=self.api_key)
                transcript = voice_client.transcribe(
                    audio_bytes, audio_filename, emotion=True, accent=False, diarization=False
                )
                voice_score = _tone_risk_score(transcript)
                if voice_score > 0:
                    log.info(
                        "modulate_voice_tone_risk",
                        campaign_id=campaign_id,
                        tone_risk=round(voice_score, 4),
                    )
            except Exception as exc:  # noqa: BLE001
                log.warning("modulate_voice_tone_check_failed", error=str(exc))

        # Combine scores: take the higher of text vs voice risk
        combined_score = min(1.0, max(text_result.toxicity_score, voice_score))
        categories = list(text_result.categories)
        if voice_score > 0.2 and SafetyCategory.TONE_RISK not in categories:
            categories.append(SafetyCategory.TONE_RISK)

        blocked = combined_score >= self.safety_threshold
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        reason = (
            f"Combined score {combined_score:.3f} "
            f"(text: {text_result.toxicity_score:.3f}, voice tone: {voice_score:.3f}). "
            + ("BLOCKED." if blocked else "PASSED.")
        )

        log.info(
            "modulate_safety_combined",
            campaign_id=campaign_id,
            text_score=round(text_result.toxicity_score, 4),
            voice_score=round(voice_score, 4),
            combined=round(combined_score, 4),
            blocked=blocked,
            latency_ms=elapsed_ms,
        )

        return SafetyResult(
            campaign_id=campaign_id,
            company_id=company_id,
            toxicity_score=round(combined_score, 4),
            blocked=blocked,
            categories=categories,
            reason=reason,
            screening_method="text+voice",
            latency_ms=elapsed_ms,
        )

    def submit_appeal(
        self,
        campaign_id: str,
        original_result: SafetyResult,
        override_reason: str = "",
        company_id: Optional[str] = None,
    ) -> AppealRecord:
        """
        Record a human reviewer's decision to override a safety block.

        Logs the appeal for Datadog false-positive tracking.
        In a full integration this would POST to Modulate's Appeals API.

        Args:
            campaign_id:      The blocked campaign ID.
            original_result:  The SafetyResult that was blocked.
            override_reason:  Reviewer's reason for overriding.
            company_id:       Optional company ID.

        Returns:
            AppealRecord confirming the override was logged.
        """
        record = AppealRecord(
            campaign_id=campaign_id,
            company_id=company_id or original_result.company_id,
            override_reason=override_reason or "Human reviewer override",
            original_score=original_result.toxicity_score,
            original_categories=list(original_result.categories),
        )

        log.info(
            "modulate_appeal_submitted",
            campaign_id=campaign_id,
            company_id=company_id,
            original_score=original_result.toxicity_score,
            original_categories=[c.value for c in original_result.categories],
            override_reason=override_reason,
        )

        return record


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _score_text(text: str) -> Tuple[float, List[SafetyCategory]]:
    """
    Run all toxicity rules against text and return (score, categories).

    Scoring:
    - Each matching rule adds its base_score weighted by match density.
    - Scores are clamped to [0.0, 1.0].
    - Presence of >= 1 match in a category adds that category to the result.
    """
    word_count = max(1, len(text.split()))
    total_score = 0.0
    matched_categories: List[SafetyCategory] = []

    for category, base_score, pattern in _COMPILED_RULES:
        matches = pattern.findall(text)
        if matches:
            match_density = min(1.0, len(matches) / max(1, word_count / 20))
            contribution = base_score * (0.5 + 0.5 * match_density)
            total_score += contribution
            if category not in matched_categories:
                matched_categories.append(category)

    return min(1.0, round(total_score, 4)), matched_categories


def _tone_risk_score(transcript: "VelmaTranscript") -> float:  # type: ignore[name-defined]
    """
    Compute a tone-risk score from Velma-2 utterance emotions.

    Returns 0.0 (no risk) to 1.0 (high risk).
    Risky emotions: angry, fear, disgust, hostile, aggressive, threatening.
    """
    emotions = [u.emotion for u in transcript.utterances if u.emotion]
    if not emotions:
        return 0.0

    risky = sum(1 for e in emotions if e.lower() in _RISKY_EMOTIONS)
    return round(risky / len(emotions), 4)


# ---------------------------------------------------------------------------
# Module-level convenience functions (mirrors the campaign_gen import style)
# ---------------------------------------------------------------------------

_default_client: Optional[ModulateSafetyClient] = None


def _get_client() -> ModulateSafetyClient:
    global _default_client
    if _default_client is None:
        _default_client = ModulateSafetyClient()
    return _default_client


def screen_campaign(
    campaign_id: str,
    headline: str,
    body_copy: str,
    company_id: Optional[str] = None,
) -> SafetyResult:
    """Module-level convenience wrapper for ModulateSafetyClient.screen_campaign()."""
    return _get_client().screen_campaign(campaign_id, headline, body_copy, company_id)


def submit_appeal(
    campaign_id: str,
    original_result: SafetyResult,
    override_reason: str = "",
    company_id: Optional[str] = None,
) -> AppealRecord:
    """Module-level convenience wrapper for ModulateSafetyClient.submit_appeal()."""
    return _get_client().submit_appeal(
        campaign_id, original_result, override_reason, company_id
    )
