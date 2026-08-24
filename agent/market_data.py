"""Market data snapshots for the risk layer.

Primary source is ASI:One; per current setup status the ASI:One uAgent
integration is still being finalized, so `AsiOneFeed` is a thin client
against its documented request/response shape but is not yet exercised
against a live endpoint. `PionexMarketDataFeed` is a working fallback built
on the public (unauthenticated, unsigned) `market` namespace of the Pionex
US client, so the agent loop has real price/spread/volume data to develop
and test the risk layer against even before ASI:One access and Pionex
trade-only keys are both in place.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests

from agent.config import AsiOneConfig
from agent.pionex_client import PionexUSClient


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    price: float
    spread: float
    volume: float
    volatility: float
    source: str


class MarketDataFeed(Protocol):
    def get_snapshot(self, symbol: str) -> MarketSnapshot: ...


class AsiOneNotConfiguredError(RuntimeError):
    pass


class AsiOneFeed:
    """Client for ASI:One's market-data endpoint.

    TODO(final setup): confirm the actual ASI:One request/response schema
    once the uAgent handshake is finished, and adjust `_parse` accordingly.
    """

    def __init__(self, config: AsiOneConfig | None = None, session: requests.Session | None = None) -> None:
        from agent.config import CONFIG

        self._config = config or CONFIG.asi_one
        self._session = session or requests.Session()

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        if not self._config.is_configured:
            raise AsiOneNotConfiguredError(
                "ASI_ONE_ENDPOINT / ASI_ONE_API_KEY are not set; "
                "ASI:One uAgent setup is not finalized yet"
            )
        response = self._session.get(
            f"{self._config.endpoint}/market/snapshot",
            params={"symbol": symbol},
            headers={"Authorization": f"Bearer {self._config.api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        return self._parse(symbol, response.json())

    @staticmethod
    def _parse(symbol: str, payload: dict) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            price=float(payload["price"]),
            spread=float(payload["spread"]),
            volume=float(payload["volume"]),
            volatility=float(payload["volatility"]),
            source="asi_one",
        )


class PionexMarketDataFeed:
    """Fallback feed built from Pionex US public ticker + order book data."""

    def __init__(self, client: PionexUSClient | None = None) -> None:
        self._client = client or PionexUSClient()

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        ticker = self._client.get_ticker(symbol)
        book = self._client.get_order_book(symbol, depth=5)

        best_bid = float(book["bids"][0][0])
        best_ask = float(book["asks"][0][0])
        price = float(ticker.get("close", (best_bid + best_ask) / 2))
        spread = (best_ask - best_bid) / price if price else 0.0
        volume = float(ticker.get("volume", 0.0))
        high = float(ticker.get("high", price))
        low = float(ticker.get("low", price))
        volatility = (high - low) / price if price else 0.0

        return MarketSnapshot(
            symbol=symbol,
            price=price,
            spread=spread,
            volume=volume,
            volatility=volatility,
            source="pionex_us",
        )


class FallbackMarketDataFeed:
    """Prefers ASI:One; falls back to Pionex public market data on failure."""

    def __init__(self, primary: MarketDataFeed | None = None, fallback: MarketDataFeed | None = None) -> None:
        self._primary = primary or AsiOneFeed()
        self._fallback = fallback or PionexMarketDataFeed()

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        try:
            return self._primary.get_snapshot(symbol)
        except (AsiOneNotConfiguredError, requests.RequestException):
            return self._fallback.get_snapshot(symbol)
