"""Risk management: Kelly, position limits, stop-loss."""
from dataclasses import dataclass


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_position_pct: float = 0.02  # max 2% of portfolio per market
    max_portfolio_pct: float = 0.10  # max 10% in single position
    max_positions: int = 10
    stop_loss_pct: float = 0.20  # -20% from entry
    take_profit_pct: float = 1.0  # 100% (e.g. double)
    kelly_fraction: float = 0.5  # half-Kelly


def kelly_fraction(p: float, q: float) -> float:
    """Kelly: f = p - (1-p)/q where q = win/loss ratio."""
    if q <= 0:
        return 0.0
    return max(0.0, p - (1 - p) / q)


def position_size(
    capital: float,
    prediction: float,
    win_loss_ratio: float = 2.0,
    config: RiskConfig | None = None,
) -> float:
    """Compute position size using fractional Kelly and limits."""
    config = config or RiskConfig()
    kf = kelly_fraction(prediction, win_loss_ratio) * config.kelly_fraction
    size = capital * min(kf, config.max_position_pct)
    return min(size, capital * config.max_portfolio_pct)


def should_stop_loss(entry_price: float, current_price: float, config: RiskConfig) -> bool:
    """True if stop-loss triggered."""
    if entry_price <= 0:
        return False
    pnl_pct = (current_price - entry_price) / entry_price
    return pnl_pct <= -config.stop_loss_pct


def should_take_profit(entry_price: float, current_price: float, config: RiskConfig) -> bool:
    """True if take-profit triggered."""
    if entry_price <= 0:
        return False
    pnl_pct = (current_price - entry_price) / entry_price
    return pnl_pct >= config.take_profit_pct
