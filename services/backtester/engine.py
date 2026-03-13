"""Backtest engine - simulates trading on historical data."""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class BacktestConfig:
    """Backtest configuration.

    sharpe_annualization: factor to annualize Sharpe ratio.
      sqrt(252)          ~15.87  for daily data
      sqrt(252*24)       ~77.77  for hourly data
      sqrt(252*24*60)   ~602.4   for minute data
      1.0                        for no annualization (raw ratio)
    Default assumes ~hourly data points from Polymarket price history.
    Override via env SHARPE_ANNUALIZATION or constructor.
    """
    initial_capital: float = 10000.0
    fee_bps: int = 30
    slippage_bps: int = 10
    position_pct: float = 0.10
    sharpe_annualization: float = (252 * 24) ** 0.5


@dataclass
class BacktestResult:
    """Backtest result with equity curve and metrics."""
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    num_trades: int = 0


def run_backtest(
    prices: pd.DataFrame,
    signals: pd.Series,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """
    Run backtest. prices: DataFrame with ts, price. signals: 1=buy, -1=sell, 0=hold.
    """
    config = config or BacktestConfig()
    capital = config.initial_capital
    position = 0.0
    equity = [capital]
    timestamps = [prices["ts"].iloc[0] if "ts" in prices.columns else 0]
    fee_mult = config.fee_bps / 10000
    slippage_mult = config.slippage_bps / 10000
    num_trades = 0

    price_col = "price" if "price" in prices.columns else prices.columns[0]
    for i in range(len(prices)):
        p = prices[price_col].iloc[i]
        ts = prices["ts"].iloc[i] if "ts" in prices.columns else i
        sig = signals.iloc[i] if i < len(signals) else 0

        if sig == 1 and position == 0 and capital > 0:  # buy
            trade_val = capital * config.position_pct
            exec_price = p * (1 + slippage_mult)
            fee = trade_val * fee_mult
            cost = trade_val + fee
            if cost <= capital:
                position = trade_val / exec_price
                capital -= cost
                num_trades += 1
        elif sig == -1 and position > 0:
            exec_price = p * (1 - slippage_mult)
            proceeds = position * exec_price
            fee = proceeds * fee_mult
            capital += proceeds - fee
            position = 0
            num_trades += 1

        portfolio_val = capital + position * p
        equity.append(portfolio_val)
        timestamps.append(ts)

    eq_series = pd.Series(equity[1:], index=timestamps[1:])
    total_return = (eq_series.iloc[-1] - config.initial_capital) / config.initial_capital if len(eq_series) > 0 else 0
    returns = eq_series.pct_change().dropna()
    sharpe = (
        returns.mean() / returns.std() * config.sharpe_annualization
        if len(returns) > 0 and returns.std() > 0
        else 0.0
    )
    cummax = eq_series.cummax()
    drawdown = (eq_series - cummax) / cummax.replace(0, float("inf"))
    max_dd = drawdown.min() if len(drawdown) > 0 else 0.0

    return BacktestResult(
        equity_curve=pd.DataFrame({"ts": eq_series.index, "equity": eq_series.values}),
        total_return=total_return,
        sharpe_ratio=float(sharpe),
        max_drawdown=float(max_dd),
        num_trades=num_trades,
    )


def baseline_always_buy(df: pd.DataFrame) -> pd.Series:
    """Baseline signal: always buy (1)."""
    return pd.Series(1, index=df.index)
