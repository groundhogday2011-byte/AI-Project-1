from unittest.mock import MagicMock

import pytest

from agent.config import PionexConfig
from agent.pionex_client import (
    PionexCredentialsMissingError,
    PionexUSClient,
    ScopeViolationError,
    _build_path,
)
from agent.rate_limiter import TokenBucketRateLimiter


def _client(**config_overrides) -> tuple[PionexUSClient, MagicMock]:
    config = PionexConfig(
        base_url="https://api.webot.com",
        api_key=config_overrides.get("api_key"),
        api_secret=config_overrides.get("api_secret"),
        requests_per_second=1000,
    )
    session = MagicMock()
    client = PionexUSClient(
        config=config,
        rate_limiter=TokenBucketRateLimiter(1000),
        session=session,
    )
    return client, session


@pytest.mark.parametrize("namespace", ["fiat", "asset"])
def test_build_path_rejects_excluded_namespaces(namespace):
    with pytest.raises(ScopeViolationError):
        _build_path(namespace, "anything")


@pytest.mark.parametrize("namespace", ["market", "trade"])
def test_build_path_allows_trading_namespaces(namespace):
    path = _build_path(namespace, "route")
    assert path == f"/api/v1/{namespace}/route"


def test_client_has_no_fiat_or_wallet_methods():
    public_methods = {name for name in dir(PionexUSClient) if not name.startswith("_")}
    forbidden_terms = ("fiat", "withdraw", "deposit", "wallet", "balance", "convert")
    offending = [m for m in public_methods for term in forbidden_terms if term in m.lower()]
    assert offending == []


def test_signed_call_without_credentials_raises_before_any_network_call():
    client, session = _client(api_key=None, api_secret=None)
    with pytest.raises(PionexCredentialsMissingError):
        client.get_open_orders()
    session.request.assert_not_called()


def test_unsigned_market_call_does_not_require_credentials():
    client, session = _client(api_key=None, api_secret=None)
    session.request.return_value = MagicMock(status_code=200, json=lambda: {"price": "1"})
    client.get_ticker("XRP_USDT")
    session.request.assert_called_once()
    method, url = session.request.call_args.args[0], session.request.call_args.args[1]
    assert method == "GET"
    assert "/api/v1/market/tickers" in url
