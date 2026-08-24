"""Trade decision/execution logging to the ICP Storage canister.

Mirrors the existing storeMemoryRequest()-style write-then-forget pattern:
every trade decision (approved or rejected by the risk layer) and every
execution result is logged, never silently dropped. Until
`ICP_TRADE_LOG_CANISTER_ID` / `ICP_IDENTITY_PEM_PATH` are configured, records
go to a local JSONL fallback so nothing is lost during bring-up; once the
canister is live, `IcpTradeLogger.log_trade` calls its `logTrade` method
(see `backend/main.mo`) via `ic-py`.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from agent.config import IcpLoggerConfig


@dataclass(frozen=True)
class TradeLogRecord:
    timestamp_ms: int
    symbol: str
    side: str
    decision: str  # "approved" | "rejected" | "executed" | "failed"
    reason: str
    notional_usd: float
    order_id: str | None = None

    @staticmethod
    def now(symbol: str, side: str, decision: str, reason: str, notional_usd: float, order_id: str | None = None) -> "TradeLogRecord":
        return TradeLogRecord(
            timestamp_ms=int(time.time() * 1000),
            symbol=symbol,
            side=side,
            decision=decision,
            reason=reason,
            notional_usd=notional_usd,
            order_id=order_id,
        )


class IcpTradeLogger:
    def __init__(self, config: IcpLoggerConfig | None = None) -> None:
        from agent.config import CONFIG

        self._config = config or CONFIG.icp
        self._canister_client = None  # lazily constructed, only if configured

    def log_trade(self, record: TradeLogRecord) -> None:
        if self._config.is_configured:
            try:
                self._log_to_canister(record)
                return
            except Exception as exc:  # noqa: BLE001 - never lose a trade record
                self._log_to_fallback(record, error=str(exc))
                return
        self._log_to_fallback(record)

    # -- canister path -------------------------------------------------

    def _get_canister_client(self):
        if self._canister_client is None:
            from ic.agent import Agent  # type: ignore
            from ic.client import Client  # type: ignore
            from ic.identity import Identity  # type: ignore

            identity = Identity.from_pem(Path(self._config.identity_pem_path).read_text())
            self._canister_client = Agent(identity, Client(url=self._config.network_url))
        return self._canister_client

    def _log_to_canister(self, record: TradeLogRecord) -> None:
        agent = self._get_canister_client()
        agent.update_raw(self._config.canister_id, "logTrade", _encode_candid(record))

    # -- fallback path ---------------------------------------------------

    def _log_to_fallback(self, record: TradeLogRecord, error: str | None = None) -> None:
        path = Path(self._config.fallback_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(record)
        if error:
            payload["canister_error"] = error
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + os.linesep)


def _encode_candid(record: TradeLogRecord) -> bytes:
    """Candid-encodes a TradeLogRecord for the `logTrade` canister call.

    TODO: wire up ic-py's Candid encoder against backend/backend.did's
    TradeRecord type once the canister is deployed and reachable.
    """
    raise NotImplementedError(
        "Candid encoding for logTrade is not wired up yet; "
        "configure ICP_TRADE_LOG_CANISTER_ID only once this is implemented"
    )
