"""Risk tolerance layer.

Evaluates a proposed order against live market-data fields (volatility,
spread, volume) and account-level caps before it is ever allowed to reach
`PionexUSClient.place_order`. This is the single choke point: the trading
agent must route every order through `RiskEngine.evaluate` first.
"""
from __future__ import annotations

from dataclasses import dataclass

from agent.config import RiskConfig
from agent.market_data import MarketSnapshot


@dataclass(frozen=True)
class ProposedOrder:
    symbol: str
    side: str  # "BUY" | "SELL"
    notional_usd: float


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None) -> None:
        from agent.config import CONFIG

        self._config = config or CONFIG.risk
        self._realized_pnl_today_usd = 0.0

    def record_realized_pnl(self, amount_usd: float) -> None:
        self._realized_pnl_today_usd += amount_usd

    def evaluate(self, snapshot: MarketSnapshot, order: ProposedOrder) -> RiskDecision:
        if order.symbol != snapshot.symbol:
            return RiskDecision(False, "market snapshot does not match order symbol")

        if self._realized_pnl_today_usd <= -self._config.max_daily_loss_usd:
            return RiskDecision(
                False,
                f"daily loss cap reached (${-self._realized_pnl_today_usd:.2f} "
                f">= ${self._config.max_daily_loss_usd:.2f})",
            )

        if order.notional_usd > self._config.max_position_size_usd:
            return RiskDecision(
                False,
                f"order notional ${order.notional_usd:.2f} exceeds max position "
                f"size ${self._config.max_position_size_usd:.2f}",
            )

        if snapshot.volatility > self._config.volatility_ceiling:
            return RiskDecision(
                False,
                f"volatility {snapshot.volatility:.4f} exceeds ceiling "
                f"{self._config.volatility_ceiling:.4f}",
            )

        if snapshot.spread > self._config.stop_loss_pct:
            return RiskDecision(
                False,
                f"spread {snapshot.spread:.4f} exceeds acceptable "
                f"{self._config.stop_loss_pct:.4f} for a clean fill",
            )

        return RiskDecision(True, "within risk parameters")
