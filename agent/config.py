"""Environment-driven configuration.

No secret ever has a default value here: if a credential is missing, the
client that needs it must fail loudly rather than silently trade with an
empty key. Set real values via a local `.env` (see `.env.example`) or the
process environment — never commit them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class PionexConfig:
    base_url: str = os.environ.get("PIONEX_US_BASE_URL", "https://api.webot.com")
    api_key: str | None = os.environ.get("PIONEX_US_API_KEY")
    api_secret: str | None = os.environ.get("PIONEX_US_API_SECRET")
    # Shared IP-wide budget across every namespace on the account, per the
    # Pionex US Open API docs (10 req/sec, not per-endpoint).
    requests_per_second: float = float(os.environ.get("PIONEX_US_RPS", "10"))

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.api_secret)


@dataclass(frozen=True)
class AsiOneConfig:
    endpoint: str | None = os.environ.get("ASI_ONE_ENDPOINT")
    api_key: str | None = os.environ.get("ASI_ONE_API_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)


@dataclass(frozen=True)
class IcpLoggerConfig:
    canister_id: str | None = os.environ.get("ICP_TRADE_LOG_CANISTER_ID")
    identity_pem_path: str | None = os.environ.get("ICP_IDENTITY_PEM_PATH")
    network_url: str = os.environ.get("ICP_NETWORK_URL", "https://icp0.io")
    # Fallback JSONL path used whenever the canister isn't reachable/configured
    # yet, so trade decisions are never silently dropped during bring-up.
    fallback_log_path: str = os.environ.get(
        "ICP_TRADE_LOG_FALLBACK_PATH", "agent/data/trade_log.jsonl"
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.canister_id and self.identity_pem_path)


@dataclass(frozen=True)
class RiskConfig:
    max_position_size_usd: float = float(os.environ.get("RISK_MAX_POSITION_USD", "500"))
    max_daily_loss_usd: float = float(os.environ.get("RISK_MAX_DAILY_LOSS_USD", "50"))
    max_exposure_pct: float = float(os.environ.get("RISK_MAX_EXPOSURE_PCT", "0.25"))
    volatility_ceiling: float = float(os.environ.get("RISK_VOLATILITY_CEILING", "0.05"))
    stop_loss_pct: float = float(os.environ.get("RISK_STOP_LOSS_PCT", "0.02"))


@dataclass(frozen=True)
class AgentConfig:
    pionex: PionexConfig = field(default_factory=PionexConfig)
    asi_one: AsiOneConfig = field(default_factory=AsiOneConfig)
    icp: IcpLoggerConfig = field(default_factory=IcpLoggerConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    # Safety default: real orders are opt-in only, so bring-up (no Pionex
    # keys yet) can never accidentally place a live order.
    live_trading_enabled: bool = _bool_env("LIVE_TRADING_ENABLED", False)
    poll_interval_seconds: int = int(os.environ.get("AGENT_POLL_INTERVAL_SECONDS", "60"))
    trading_symbols: tuple[str, ...] = tuple(
        s.strip() for s in os.environ.get("TRADING_SYMBOLS", "XRP_USDT").split(",") if s.strip()
    )


CONFIG = AgentConfig()
