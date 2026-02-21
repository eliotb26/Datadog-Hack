"""Polymarket Gamma API client — data source for Agent 2 (Trend Intelligence).

Public API, no authentication required.
Base URL: https://gamma-api.polymarket.com
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import httpx
import structlog

log = structlog.get_logger(__name__)

POLYMARKET_BASE_URL = os.getenv("POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com")
DEFAULT_VOLUME_THRESHOLD = float(os.getenv("POLYMARKET_VOLUME_THRESHOLD", "10000"))


class PolymarketClient:
    """Async client for Polymarket Gamma API."""

    def __init__(
        self,
        base_url: str = POLYMARKET_BASE_URL,
        volume_threshold: float = DEFAULT_VOLUME_THRESHOLD,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.volume_threshold = volume_threshold
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    # ------------------------------------------------------------------
    # Raw API calls
    # ------------------------------------------------------------------

    async def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        order: str = "volume",
        ascending: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch prediction markets, sorted by volume descending by default."""
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }
        resp = await self._client.get("/markets", params=params)
        resp.raise_for_status()
        data = resp.json()
        # Gamma API returns a list directly or wraps in {"markets": [...]}
        if isinstance(data, list):
            return data
        return data.get("markets", data.get("data", []))

    async def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch prediction market events (grouped markets)."""
        resp = await self._client.get("/events", params={"limit": limit, "active": "true"})
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("events", [])

    # ------------------------------------------------------------------
    # Signal extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_probability(market: Dict[str, Any]) -> float:
        """Extract YES probability from outcomePrices field."""
        raw = market.get("outcomePrices", "[]")
        try:
            prices = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(prices, list) and prices:
                return float(prices[0])
        except (ValueError, TypeError, IndexError):
            pass
        # Fallback to bestBid/bestAsk midpoint
        try:
            bid = float(market.get("bestBid", 0) or 0)
            ask = float(market.get("bestAsk", 1) or 1)
            return (bid + ask) / 2
        except (ValueError, TypeError):
            return 0.5

    @staticmethod
    def _parse_volume(market: Dict[str, Any]) -> float:
        try:
            return float(market.get("volume", 0) or 0)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_volume_24h(market: Dict[str, Any]) -> float:
        try:
            return float(market.get("volume24hr", 0) or 0)
        except (ValueError, TypeError):
            return 0.0

    def enrich_markets(self, markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add computed fields: probability, volume_velocity, probability_momentum."""
        for m in markets:
            prob = self._parse_probability(m)
            volume = self._parse_volume(m)
            volume_24h = self._parse_volume_24h(m)

            m["probability"] = prob
            m["volume"] = volume
            # velocity = fraction of total volume traded in last 24h
            m["volume_velocity"] = volume_24h / max(volume, 1.0) if volume > 0 else 0.0
            # momentum: abs deviation from 0.5 (markets moving away from coin-flip are more interesting)
            last_price = float(m.get("lastTradePrice", prob) or prob)
            m["probability_momentum"] = abs(prob - last_price)
        return markets

    def filter_high_momentum(self, markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep only markets above the volume threshold."""
        return [m for m in markets if m.get("volume", 0) >= self.volume_threshold]

    # ------------------------------------------------------------------
    # Main entry-point used by Agent 2 tools
    # ------------------------------------------------------------------

    async def fetch_top_signals(
        self,
        limit: int = 100,
        top_n: int = 20,
        volume_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch, enrich and filter Polymarket markets.

        Returns up to `top_n` markets ranked by (volume_velocity + probability_momentum).
        """
        threshold = volume_threshold if volume_threshold is not None else self.volume_threshold
        log.info("fetching_polymarket_markets", limit=limit, threshold=threshold)

        try:
            markets = await self.get_markets(limit=limit)
        except httpx.HTTPError as exc:
            log.error("polymarket_api_error", error=str(exc))
            raise

        markets = self.enrich_markets(markets)
        markets = [m for m in markets if m.get("volume", 0) >= threshold]

        # Rank by composite momentum score
        markets.sort(
            key=lambda m: m.get("volume_velocity", 0) + m.get("probability_momentum", 0),
            reverse=True,
        )
        result = markets[:top_n]
        log.info("polymarket_signals_fetched", count=len(result))
        return result

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "PolymarketClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
