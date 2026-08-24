from agent.config import RiskConfig
from agent.market_data import MarketSnapshot
from agent.risk import ProposedOrder, RiskEngine


def _snapshot(**overrides) -> MarketSnapshot:
    defaults = dict(symbol="XRP_USDT", price=2.0, spread=0.001, volume=1000.0, volatility=0.01, source="test")
    defaults.update(overrides)
    return MarketSnapshot(**defaults)


def _config(**overrides) -> RiskConfig:
    defaults = dict(
        max_position_size_usd=500,
        max_daily_loss_usd=50,
        max_exposure_pct=0.25,
        volatility_ceiling=0.05,
        stop_loss_pct=0.02,
    )
    defaults.update(overrides)
    return RiskConfig(**defaults)


def test_approves_order_within_limits():
    engine = RiskEngine(_config())
    decision = engine.evaluate(_snapshot(), ProposedOrder("XRP_USDT", "BUY", 50.0))
    assert decision.approved is True


def test_rejects_order_exceeding_position_size():
    engine = RiskEngine(_config(max_position_size_usd=10))
    decision = engine.evaluate(_snapshot(), ProposedOrder("XRP_USDT", "BUY", 50.0))
    assert decision.approved is False
    assert "position" in decision.reason


def test_rejects_when_daily_loss_cap_hit():
    engine = RiskEngine(_config(max_daily_loss_usd=20))
    engine.record_realized_pnl(-25.0)
    decision = engine.evaluate(_snapshot(), ProposedOrder("XRP_USDT", "BUY", 10.0))
    assert decision.approved is False
    assert "daily loss" in decision.reason


def test_rejects_when_volatility_too_high():
    engine = RiskEngine(_config(volatility_ceiling=0.01))
    decision = engine.evaluate(_snapshot(volatility=0.05), ProposedOrder("XRP_USDT", "BUY", 10.0))
    assert decision.approved is False
    assert "volatility" in decision.reason


def test_rejects_when_spread_too_wide():
    engine = RiskEngine(_config(stop_loss_pct=0.001))
    decision = engine.evaluate(_snapshot(spread=0.01), ProposedOrder("XRP_USDT", "BUY", 10.0))
    assert decision.approved is False
    assert "spread" in decision.reason


def test_rejects_symbol_mismatch():
    engine = RiskEngine(_config())
    decision = engine.evaluate(_snapshot(symbol="BTC_USDT"), ProposedOrder("XRP_USDT", "BUY", 10.0))
    assert decision.approved is False
