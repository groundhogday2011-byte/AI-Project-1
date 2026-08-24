"""Fetch.ai uAgent that polls market data, applies the risk layer, and
(only when explicitly enabled) places trades on Pionex US.

Every decision — approved, rejected, executed, or failed — is logged via
`IcpTradeLogger`, and no order reaches `PionexUSClient.place_order` without
first clearing `RiskEngine.evaluate`. `LIVE_TRADING_ENABLED` defaults to
false (see agent/config.py), so this runs in dry-run/paper mode until it is
turned on deliberately with real Pionex US trade-only keys in place.
"""
from __future__ import annotations

import logging

from uagents import Agent, Context

from agent.config import CONFIG
from agent.icp_logger import IcpTradeLogger, TradeLogRecord
from agent.market_data import FallbackMarketDataFeed, MarketSnapshot
from agent.pionex_client import OrderRequest, PionexAPIError, PionexUSClient
from agent.risk import ProposedOrder, RiskDecision, RiskEngine

logger = logging.getLogger("webot_trading_agent")

trading_agent = Agent(
    name="webot_trading_agent",
    seed="webot-trading-agent-seed",  # override via AGENT_SEED for a stable identity in production
)

_market_data = FallbackMarketDataFeed()
_risk_engine = RiskEngine()
_pionex_client = PionexUSClient()
_trade_logger = IcpTradeLogger()


def decide_order(snapshot: MarketSnapshot) -> ProposedOrder:
    """Placeholder sizing strategy: flat notional buy, capped by risk config.

    Replace with real signal generation once ASI:One market data is fully
    wired and a strategy is defined; this exists so the risk layer and
    logging path can be exercised end-to-end today.
    """
    return ProposedOrder(
        symbol=snapshot.symbol,
        side="BUY",
        notional_usd=min(50.0, CONFIG.risk.max_position_size_usd),
    )


async def evaluate_symbol(ctx: Context, symbol: str) -> None:
    try:
        snapshot = _market_data.get_snapshot(symbol)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.warning(f"could not fetch market snapshot for {symbol}: {exc}")
        return

    order = decide_order(snapshot)
    decision: RiskDecision = _risk_engine.evaluate(snapshot, order)

    if not decision.approved:
        ctx.logger.info(f"[{symbol}] rejected: {decision.reason}")
        _trade_logger.log_trade(
            TradeLogRecord.now(symbol, order.side, "rejected", decision.reason, order.notional_usd)
        )
        return

    ctx.logger.info(f"[{symbol}] approved: {decision.reason}")
    _trade_logger.log_trade(
        TradeLogRecord.now(symbol, order.side, "approved", decision.reason, order.notional_usd)
    )

    if not CONFIG.live_trading_enabled:
        ctx.logger.info(f"[{symbol}] live trading disabled; skipping order placement")
        return

    size = str(order.notional_usd / snapshot.price)
    try:
        result = _pionex_client.place_order(
            OrderRequest(symbol=symbol, side=order.side, order_type="MARKET", size=size)
        )
        order_id = result.get("orderId") if isinstance(result, dict) else None
        _trade_logger.log_trade(
            TradeLogRecord.now(symbol, order.side, "executed", "order placed", order.notional_usd, order_id)
        )
    except PionexAPIError as exc:
        ctx.logger.error(f"[{symbol}] order failed: {exc}")
        _trade_logger.log_trade(
            TradeLogRecord.now(symbol, order.side, "failed", str(exc), order.notional_usd)
        )


@trading_agent.on_interval(period=float(CONFIG.poll_interval_seconds))
async def poll_and_trade(ctx: Context) -> None:
    for symbol in CONFIG.trading_symbols:
        await evaluate_symbol(ctx, symbol)


@trading_agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    ctx.logger.info(
        f"webot_trading_agent starting: symbols={CONFIG.trading_symbols} "
        f"live_trading_enabled={CONFIG.live_trading_enabled} "
        f"pionex_credentials={CONFIG.pionex.has_credentials} "
        f"asi_one_configured={CONFIG.asi_one.is_configured}"
    )


if __name__ == "__main__":
    trading_agent.run()
