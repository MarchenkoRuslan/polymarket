"""Tests for risk management."""
from services.execution_bot.risk import (
    kelly_fraction,
    position_size,
    RiskConfig,
    should_stop_loss,
    should_take_profit,
)
from services.execution_bot.main import _limit_price, _parse_int


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


def test_stop_loss_zero_entry():
    """Stop-loss with zero entry price never triggers."""
    cfg = RiskConfig(stop_loss_pct=0.2)
    assert should_stop_loss(0, 0.5, cfg) is False


def test_limit_price_buy_applies_discount():
    """Buy limit price is below prediction (edge discount)."""
    price = _limit_price(0.7, "buy")
    assert price < 0.7


def test_limit_price_sell_applies_premium():
    """Sell limit price is above prediction."""
    price = _limit_price(0.3, "sell")
    assert price > 0.3


def test_parse_int_valid(monkeypatch):
    """_parse_int reads valid env."""
    monkeypatch.setenv("TEST_PORT", "9090")
    assert _parse_int("TEST_PORT", "8000") == 9090


def test_parse_int_invalid_falls_back(monkeypatch):
    """_parse_int with invalid env returns default."""
    monkeypatch.setenv("TEST_PORT", "not_a_number")
    assert _parse_int("TEST_PORT", "8000") == 8000


def test_parse_int_missing_uses_default(monkeypatch):
    """_parse_int with missing env returns default."""
    monkeypatch.delenv("TEST_PORT_MISSING", raising=False)
    assert _parse_int("TEST_PORT_MISSING", "42") == 42
