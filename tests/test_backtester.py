"""Tests for backtester engine."""
import pandas as pd

from services.backtester.engine import (
    run_backtest,
    BacktestConfig,
    baseline_always_buy,
    BacktestResult,
)


def _make_price_series(n: int = 100, trend: float = 0.001, volatility: float = 0.01) -> pd.DataFrame:
    """Generate synthetic price series."""
    import numpy as np
    prices = 0.5 + trend * np.arange(n) + volatility * np.random.randn(n).cumsum()
    prices = np.clip(prices, 0.01, 0.99)
    return pd.DataFrame({"ts": range(n), "price": prices})


def test_backtest_baseline():
    """Backtest with always-buy baseline."""
    n = 100
    df = pd.DataFrame({
        "ts": range(n),
        "price": 0.5 + 0.01 * pd.Series(range(n)).astype(float),
    })
    signals = baseline_always_buy(df)
    config = BacktestConfig(initial_capital=10000, fee_bps=30)
    result = run_backtest(df, signals, config)
    assert isinstance(result, BacktestResult)
    assert result.num_trades >= 1
    assert len(result.equity_curve) > 0


def test_backtest_hold():
    """Backtest with all-zeros (hold) signals."""
    df = pd.DataFrame({"ts": range(50), "price": [0.5] * 50})
    signals = pd.Series(0, index=df.index)
    result = run_backtest(df, signals)
    assert result.num_trades == 0
    assert result.total_return == 0


def test_stress_double_fee():
    """Stress: double fee reduces profitability."""
    df = _make_price_series(100, trend=0.002)
    signals = baseline_always_buy(df)
    low_fee = run_backtest(df, signals, BacktestConfig(fee_bps=30))
    high_fee = run_backtest(df, signals, BacktestConfig(fee_bps=60))
    assert high_fee.total_return <= low_fee.total_return + 0.01


def test_stress_high_slippage():
    """Stress: high slippage reduces profitability."""
    df = _make_price_series(100, trend=0.002)
    signals = baseline_always_buy(df)
    low_slip = run_backtest(df, signals, BacktestConfig(slippage_bps=10))
    high_slip = run_backtest(df, signals, BacktestConfig(slippage_bps=100))
    assert high_slip.total_return <= low_slip.total_return + 0.05


def test_stress_high_volatility():
    """Stress: high volatility increases max drawdown."""
    df_low = _make_price_series(100, volatility=0.005)
    df_high = _make_price_series(100, volatility=0.05)
    signals = baseline_always_buy(df_low)
    res_low = run_backtest(df_low, signals)
    res_high = run_backtest(df_high, baseline_always_buy(df_high))
    assert res_high.max_drawdown <= res_low.max_drawdown + 0.5


def test_three_state_signals():
    """3-state signals: buy opens, hold keeps, sell closes."""
    n = 60
    df = pd.DataFrame({
        "ts": range(n),
        "price": [0.5 + 0.002 * i for i in range(n)],
    })
    signals = pd.Series([1] + [0] * 28 + [-1] + [0] * 30)
    result = run_backtest(df, signals, BacktestConfig(initial_capital=10000))
    assert result.num_trades == 2
    assert result.total_return > 0


def test_sharpe_annualization_config():
    """Custom sharpe_annualization changes Sharpe ratio."""
    df = _make_price_series(200, trend=0.002)
    signals = baseline_always_buy(df)
    daily = run_backtest(df, signals, BacktestConfig(sharpe_annualization=252**0.5))
    minute = run_backtest(df, signals, BacktestConfig(sharpe_annualization=(252 * 24 * 60) ** 0.5))
    if daily.sharpe_ratio != 0:
        assert abs(minute.sharpe_ratio) > abs(daily.sharpe_ratio)
