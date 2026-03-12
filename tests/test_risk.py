"""Tests for risk management."""
from services.execution_bot.risk import (
    kelly_fraction,
    position_size,
    RiskConfig,
    should_stop_loss,
    should_take_profit,
)


def test_kelly_fraction():
    """Kelly formula: f = p - (1-p)/q."""
    assert kelly_fraction(0.6, 2.0) > 0
    assert kelly_fraction(0.5, 1.0) == 0
    # p=0.4, q=2 => f = 0.4 - 0.6/2 = 0.1
    assert kelly_fraction(0.4, 2.0) > 0
    # Low p or low q => negative/zero
    assert kelly_fraction(0.3, 1.0) == 0


def test_position_size():
    """Position size respects limits."""
    cfg = RiskConfig(max_position_pct=0.02)
    size = position_size(10000, 0.7, win_loss_ratio=2.0, config=cfg)
    assert 0 <= size <= 10000 * 0.02


def test_stop_loss():
    """Stop-loss triggers."""
    cfg = RiskConfig(stop_loss_pct=0.2)
    assert should_stop_loss(1.0, 0.79, cfg) is True
    assert should_stop_loss(1.0, 0.85, cfg) is False


def test_take_profit():
    """Take-profit triggers."""
    cfg = RiskConfig(take_profit_pct=1.0)
    assert should_take_profit(1.0, 2.0, cfg) is True
    assert should_take_profit(1.0, 1.5, cfg) is False
