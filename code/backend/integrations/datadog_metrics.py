from __future__ import annotations

from typing import Any, Callable


def _noop(*args: Any, **kwargs: Any) -> None:
    return None


def timed(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        return fn
    return _decorator


track_api_call = _noop
track_trend_agent_run = _noop
track_campaign_agent_run = _noop
track_campaign_generated = _noop
track_campaign_approved = _noop
track_campaign_blocked_safety = _noop
track_modulate_safety_check = _noop
track_agent_run = _noop
track_signals_surfaced = _noop
track_polymarket_poll = _noop
track_polymarket_error = _noop
track_feedback_loop = _noop
track_prompt_quality = _noop
track_weight_update = _noop
track_modulate_appeal = _noop
track_modulate_voice_brief = _noop
track_agent_latency = _noop
track_agent_tokens = _noop
track_agent_error = _noop
