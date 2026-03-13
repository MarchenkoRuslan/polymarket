"""Feature calculation: MA, volatility, volume, RSI, MACD, spread."""
import pandas as pd


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI = 100 - 100/(1 + RS) using Wilder's smoothing (EMA with alpha=1/period)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_price_features(df: pd.DataFrame, price_col: str = "price") -> pd.DataFrame:
    """Compute price-based features: MA, volatility, ROC, RSI, MACD."""
    out = df.copy()
    p = out[price_col]
    out["ma_1h"] = p.rolling(window=60, min_periods=1).mean()
    out["ma_5m"] = p.rolling(window=5, min_periods=1).mean()
    out["volatility_1h"] = p.pct_change().rolling(window=60, min_periods=2).std()
    out["roc_1h"] = (p - p.shift(60)) / p.shift(60).replace(0, 1e-9)
    out["rsi_14"] = compute_rsi(p, 14)
    macd_line, signal_line, hist = compute_macd(p)
    out["macd"] = macd_line
    out["macd_signal"] = signal_line
    out["macd_hist"] = hist
    return out


def compute_volume_features(df: pd.DataFrame, size_col: str = "size") -> pd.DataFrame:
    """Compute volume-based features."""
    out = df.copy()
    out["volume_1h"] = out[size_col].rolling(window=60, min_periods=0).sum()
    out["volume_5m"] = out[size_col].rolling(window=5, min_periods=0).sum()
    return out


def compute_spread_features(
    df: pd.DataFrame,
    bid_col: str = "bid_price",
    ask_col: str = "ask_price",
) -> pd.DataFrame:
    """Compute bid-ask spread features. Expects bid_price, ask_price columns."""
    out = df.copy()
    if bid_col not in out.columns or ask_col not in out.columns:
        return out
    mid = (out[bid_col] + out[ask_col]) / 2
    out["spread"] = out[ask_col] - out[bid_col]
    out["spread_bps"] = (out["spread"] / mid.replace(0, 1e-9)) * 10000
    out["mid_price"] = mid
    return out


def compute_all(
    df: pd.DataFrame,
    include_orderbook: bool = False,
) -> pd.DataFrame:
    """Compute all features. Expects: ts, price, size. Optionally bid_price, ask_price."""
    df = compute_price_features(df)
    df = compute_volume_features(df)
    if include_orderbook and "bid_price" in df.columns and "ask_price" in df.columns:
        df = compute_spread_features(df)
    return df


def to_feature_rows(df: pd.DataFrame, market_id: str) -> list[dict]:
    """Convert DataFrame with feature columns to list of (market_id, ts, feature_name, value).

    Uses melt+dropna for vectorized performance instead of iterrows.
    """
    feature_cols = [c for c in df.columns if c not in ("ts", "market_id", "price", "size", "side")]
    if not feature_cols:
        return []
    melted = df[["ts"] + feature_cols].melt(id_vars=["ts"], var_name="feature_name", value_name="feature_value")
    melted = melted.dropna(subset=["feature_value"])
    melted["market_id"] = market_id
    return melted[["market_id", "ts", "feature_name", "feature_value"]].to_dict("records")
