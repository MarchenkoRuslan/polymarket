"""Load historical data from PMXT Parquet archive."""
import io
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

# New hourly format: data/data/polymarket_{table}_{YYYY-MM-DD}T{HH}.parquet
PMXT_DATA_PATH = "data/data"


def load_pmxt_parquet(
    base_url: str,
    dataset: str,
    date_str: str,
    table: str,
) -> pd.DataFrame | None:
    """
    Load Parquet file from PMXT archive (legacy daily format).
    dataset: 'Polymarket'
    table: 'orderbook', 'trades', etc.
    date_str: 'YYYY-MM-DD'
    """
    path = f"{dataset}/{date_str}/{table}.parquet"
    url = urljoin(base_url + "/", path)
    try:
        with httpx.Client() as client:
            resp = client.get(url, timeout=60)
            if resp.status_code != 200:
                logger.warning("PMXT %s: %s", url, resp.status_code)
                return None
            df = pd.read_parquet(io.BytesIO(resp.content))
            return df
    except Exception as e:
        logger.warning("PMXT load error %s: %s", url, e)
        return None


def load_pmxt_parquet_hourly(
    base_url: str,
    table: str,
    date_str: str,
    hour: int,
) -> pd.DataFrame | None:
    """
    Load hourly Parquet from PMXT archive (new format).
    table: 'orderbook' or 'trades'
    date_str: 'YYYY-MM-DD'
    hour: 0-23
    """
    filename = f"polymarket_{table}_{date_str}T{hour:02d}.parquet"
    path = f"{PMXT_DATA_PATH}/{filename}"
    url = urljoin(base_url.rstrip("/") + "/", path)
    try:
        with httpx.Client() as client:
            resp = client.get(url, timeout=120)
            if resp.status_code != 200:
                logger.debug("PMXT %s: %s", url, resp.status_code)
                return None
            ct = (resp.headers.get("content-type") or "").lower()
            if "html" in ct or resp.content[:4] == b"<!DO":
                logger.warning("PMXT %s: got HTML instead of Parquet (archive URL may have changed)", url[:80])
                return None
            df = pd.read_parquet(io.BytesIO(resp.content))
            return df
    except Exception as e:
        logger.warning("PMXT load error %s: %s", url, e)
        return None


def _parse_ts(raw_ts):
    """Parse timestamp from various PMXT formats into timezone-aware datetime.

    Returns None for unparseable values.
    """
    if raw_ts is None:
        return None
    if hasattr(raw_ts, "to_pydatetime"):
        dt = raw_ts.to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    if isinstance(raw_ts, (int, float)):
        import math
        if math.isnan(raw_ts):
            return None
        if raw_ts > 1e12:
            raw_ts = raw_ts / 1000
        return datetime.fromtimestamp(raw_ts, tz=timezone.utc)
    if isinstance(raw_ts, str):
        try:
            dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None
    if isinstance(raw_ts, datetime):
        if raw_ts.tzinfo is None:
            raw_ts = raw_ts.replace(tzinfo=timezone.utc)
        return raw_ts
    return None


def _get_ts_field(row):
    """Get timestamp field from row, checking multiple possible column names."""
    for key in ("timestamp", "ts", "t", "time"):
        val = row.get(key)
        if val is not None:
            return val
    return None


def _get_market_id(row, market_id_col: str = "market") -> str:
    """Get market_id from row with fallbacks for various PMXT column names."""
    for key in (market_id_col, "market_id", "condition_id", "market", "conditionId"):
        val = row.get(key)
        if val is not None and str(val).strip():
            return str(val)
    return ""


def trades_to_rows(df: pd.DataFrame, market_id_col: str = "market") -> list[dict]:
    """Convert PMXT trades DataFrame to list of dicts for DB insert."""
    if df is None or df.empty:
        return []
    rows = []
    for _, row in df.iterrows():
        raw_ts = _get_ts_field(row)
        ts = _parse_ts(raw_ts)
        if ts is None:
            continue
        market_id = _get_market_id(row, market_id_col)
        if not market_id:
            continue
        try:
            price = float(row.get("price", row.get("outcome_price", 0)))
            size = float(row.get("size", row.get("volume", 0)))
        except (TypeError, ValueError):
            continue
        if price != price or size != size:  # NaN check
            continue
        side = str(row.get("side", "buy"))[:4]
        rows.append({"ts": ts, "market_id": market_id, "price": price, "size": size, "side": side})
    return rows


def orderbook_to_rows(
    df: pd.DataFrame, market_id_col: str = "market"
) -> list[dict]:
    """Convert PMXT orderbook DataFrame to list of dicts for DB insert."""
    if df is None or df.empty:
        return []
    rows = []
    for _, row in df.iterrows():
        raw_ts = _get_ts_field(row)
        ts = _parse_ts(raw_ts)
        if ts is None:
            continue
        market_id = _get_market_id(row, market_id_col)
        if not market_id:
            continue
        try:
            bid_price = float(row.get("bid_price", row.get("best_bid", row.get("bid", 0))))
            bid_qty = float(row.get("bid_qty", row.get("bid_size", 0)))
            ask_price = float(row.get("ask_price", row.get("best_ask", row.get("ask", 0))))
            ask_qty = float(row.get("ask_qty", row.get("ask_size", 0)))
        except (TypeError, ValueError):
            continue
        rows.append({
            "ts": ts, "market_id": market_id,
            "bid_price": bid_price, "bid_qty": bid_qty,
            "ask_price": ask_price, "ask_qty": ask_qty,
        })
    return rows


def orderbook_to_trade_rows(df: pd.DataFrame, market_id_col: str = "market") -> list[dict]:
    """Create synthetic trade rows from orderbook (mid-price) for pipelines that need trades."""
    if df is None or df.empty:
        return []
    rows = []
    for _, row in df.iterrows():
        raw_ts = _get_ts_field(row)
        ts = _parse_ts(raw_ts)
        if ts is None:
            continue
        market_id = _get_market_id(row, market_id_col)
        if not market_id:
            continue
        try:
            bid = float(row.get("bid_price", row.get("best_bid", row.get("bid", 0))))
            ask = float(row.get("ask_price", row.get("best_ask", row.get("ask", 0))))
        except (TypeError, ValueError):
            continue
        mid = (bid + ask) / 2 if (bid and ask) else bid or ask
        if mid <= 0 or mid >= 1:
            continue
        rows.append({"ts": ts, "market_id": market_id, "price": mid, "size": 1.0, "side": "buy"})
    return rows
