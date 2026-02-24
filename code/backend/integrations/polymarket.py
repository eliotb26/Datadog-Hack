from __future__ import annotations

from typing import Any, Dict, List


class PolymarketClient:
    """Disabled sponsor client shim: returns no external-market data."""

    def __init__(self, volume_threshold: float = 0.0, volume_velocity_threshold: float = 0.0) -> None:
        self.volume_threshold = volume_threshold
        self.volume_velocity_threshold = volume_velocity_threshold

    async def __aenter__(self) -> "PolymarketClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def fetch_top_signals(
        self,
        limit: int = 50,
        top_n: int = 20,
        volume_threshold: float = 0.0,
        volume_velocity_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        return []
