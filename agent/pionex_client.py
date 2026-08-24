"""Pionex US Open API trading client.

Scope is enforced structurally, not by convention: this client only ever
builds request paths under the `market` (public market data) and `trade`
namespaces. `fiat` and `asset` (deposit/withdrawal/conversion/wallet
balance) are never implemented as methods, and `_build_path` refuses to
construct a request outside the allowlist even if a caller tries — so a
credential scoped only for trading can never be sent against those routes
from this code path.

Signing scheme: Pionex-family Open APIs sign
`METHOD + PATH + "?" + sorted_query_string` (including a `timestamp` query
param) with HMAC-SHA256 over the API secret, sent as the `PIONEX-SIGNATURE`
header alongside `PIONEX-KEY` and `PIONEX-TIMESTAMP`. This mirrors the
publicly documented Pionex Open API and is the best available assumption
until real Pionex US credentials/docs are on hand to verify it — see
`_sign()` below if it needs correcting later.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlencode

import requests

from agent.config import PionexConfig
from agent.rate_limiter import TokenBucketRateLimiter

ALLOWED_NAMESPACES = ("market", "trade")
EXCLUDED_NAMESPACES = ("fiat", "asset")


class ScopeViolationError(PermissionError):
    """Raised when code attempts to reach a non-trading namespace."""


class PionexCredentialsMissingError(RuntimeError):
    """Raised when a signed endpoint is called without API credentials configured."""


class PionexAPIError(RuntimeError):
    def __init__(self, status_code: int, payload: Any) -> None:
        super().__init__(f"Pionex US API error {status_code}: {payload}")
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str  # "BUY" | "SELL"
    order_type: str  # "MARKET" | "LIMIT"
    size: str
    price: str | None = None
    client_order_id: str | None = None


def _build_path(namespace: str, route: str) -> str:
    if namespace not in ALLOWED_NAMESPACES:
        hint = " (deposit/withdrawal/wallet routes are out of scope for this agent)" if (
            namespace in EXCLUDED_NAMESPACES
        ) else ""
        raise ScopeViolationError(
            f"refusing to build a request under namespace '{namespace}'{hint}; "
            f"only {ALLOWED_NAMESPACES} are reachable from PionexUSClient"
        )
    return f"/api/v1/{namespace}/{route.lstrip('/')}"


class PionexUSClient:
    def __init__(
        self,
        config: PionexConfig | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        session: requests.Session | None = None,
    ) -> None:
        from agent.config import CONFIG

        self._config = config or CONFIG.pionex
        self._rate_limiter = rate_limiter or TokenBucketRateLimiter(
            self._config.requests_per_second
        )
        self._session = session or requests.Session()

    # -- signing ---------------------------------------------------------

    def _sign(self, method: str, path: str, query: Mapping[str, str]) -> tuple[str, dict[str, str]]:
        if not self._config.has_credentials:
            raise PionexCredentialsMissingError(
                "PIONEX_US_API_KEY / PIONEX_US_API_SECRET are not set; "
                "signed endpoints are unavailable until trade-only keys are provisioned"
            )
        query_string = urlencode(sorted(query.items()))
        payload = f"{method.upper()}{path}?{query_string}"
        signature = hmac.new(
            self._config.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "PIONEX-KEY": self._config.api_key,
            "PIONEX-SIGNATURE": signature,
            "PIONEX-TIMESTAMP": query["timestamp"],
        }
        return query_string, headers

    # -- transport ---------------------------------------------------------

    def _request(
        self,
        method: str,
        namespace: str,
        route: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        path = _build_path(namespace, route)
        params = dict(params or {})

        self._rate_limiter.acquire()

        headers = {}
        query_string = urlencode(sorted(params.items())) if params else ""
        if signed:
            params["timestamp"] = str(int(time.time() * 1000))
            query_string, headers = self._sign(method, path, params)

        url = f"{self._config.base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"

        response = self._session.request(method, url, json=body, headers=headers, timeout=10)
        if response.status_code >= 400:
            raise PionexAPIError(response.status_code, _safe_json(response))
        return _safe_json(response)

    # -- public market data (namespace: market) ---------------------------

    def get_ticker(self, symbol: str) -> Any:
        return self._request("GET", "market", "tickers", params={"symbol": symbol})

    def get_order_book(self, symbol: str, depth: int = 20) -> Any:
        return self._request("GET", "market", "depth", params={"symbol": symbol, "limit": depth})

    def get_klines(self, symbol: str, interval: str = "1M", limit: int = 100) -> Any:
        return self._request(
            "GET", "market", "klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )

    # -- trading (namespace: trade, signed) --------------------------------

    def get_open_orders(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "trade", "openOrders", params=params, signed=True)

    def get_order(self, symbol: str, order_id: str) -> Any:
        return self._request(
            "GET", "trade", "order",
            params={"symbol": symbol, "orderId": order_id}, signed=True,
        )

    def place_order(self, order: OrderRequest) -> Any:
        body: dict[str, Any] = {
            "symbol": order.symbol,
            "side": order.side,
            "type": order.order_type,
            "size": order.size,
        }
        if order.price is not None:
            body["price"] = order.price
        if order.client_order_id is not None:
            body["clientOrderId"] = order.client_order_id
        return self._request("POST", "trade", "order", body=body, signed=True)

    def cancel_order(self, symbol: str, order_id: str) -> Any:
        return self._request(
            "DELETE", "trade", "order",
            params={"symbol": symbol, "orderId": order_id}, signed=True,
        )


def _safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}
