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

    col_map = {c: i for i, c in enumerate(df.columns)}
    ts_keys = ("timestamp", "ts", "t", "time")
    mid_keys = (market_id_col, "market_id", "condition_id", "market", "conditionId")

    rows = []
    for tup in df.itertuples(index=False):
        raw_ts = next((tup[col_map[k]] for k in ts_keys if k in col_map and tup[col_map[k]] is not None), None)
        ts = _parse_ts(raw_ts)
        if ts is None:
            continue
        market_id = ""
        for k in mid_keys:
            if k in col_map:
                v = tup[col_map[k]]
                if v is not None and str(v).strip():
                    market_id = str(v)
                    break
        if not market_id:
            continue
        try:
            price = float(tup[col_map["price"]] if "price" in col_map else (tup[col_map["outcome_price"]] if "outcome_price" in col_map else 0))
            size = float(tup[col_map["size"]] if "size" in col_map else (tup[col_map["volume"]] if "volume" in col_map else 0))
        except (TypeError, ValueError):
            continue
        if price != price or size != size:
            continue
        side_val = tup[col_map["side"]] if "side" in col_map else "buy"
        side = str(side_val)[:4] if side_val else "buy"
        rows.append({"ts": ts, "market_id": market_id, "price": price, "size": size, "side": side})
    return rows


def orderbook_to_rows(
    df: pd.DataFrame, market_id_col: str = "market"
) -> list[dict]:
    """Convert PMXT orderbook DataFrame to list of dicts for DB insert."""
    if df is None or df.empty:
        return []
    col_map = {c: i for i, c in enumerate(df.columns)}
    ts_keys = ("timestamp", "ts", "t", "time")
    mid_keys = (market_id_col, "market_id", "condition_id", "market", "conditionId")

    def _col(tup, *keys, default=0):
        for k in keys:
            if k in col_map and tup[col_map[k]] is not None:
                return tup[col_map[k]]
        return default

    rows = []
    for tup in df.itertuples(index=False):
        raw_ts = next((tup[col_map[k]] for k in ts_keys if k in col_map and tup[col_map[k]] is not None), None)
        ts = _parse_ts(raw_ts)
        if ts is None:
            continue
        market_id = ""
        for k in mid_keys:
            if k in col_map:
                v = tup[col_map[k]]
                if v is not None and str(v).strip():
                    market_id = str(v)
                    break
        if not market_id:
            continue
        try:
            bid_price = float(_col(tup, "bid_price", "best_bid", "bid"))
            bid_qty = float(_col(tup, "bid_qty", "bid_size"))
            ask_price = float(_col(tup, "ask_price", "best_ask", "ask"))
            ask_qty = float(_col(tup, "ask_qty", "ask_size"))
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
    col_map = {c: i for i, c in enumerate(df.columns)}
    ts_keys = ("timestamp", "ts", "t", "time")
    mid_keys = (market_id_col, "market_id", "condition_id", "market", "conditionId")

    def _col(tup, *keys, default=0):
        for k in keys:
            if k in col_map and tup[col_map[k]] is not None:
                return tup[col_map[k]]
        return default

    rows = []
    for tup in df.itertuples(index=False):
        raw_ts = next((tup[col_map[k]] for k in ts_keys if k in col_map and tup[col_map[k]] is not None), None)
        ts = _parse_ts(raw_ts)
        if ts is None:
            continue
        market_id = ""
        for k in mid_keys:
            if k in col_map:
                v = tup[col_map[k]]
                if v is not None and str(v).strip():
                    market_id = str(v)
                    break
        if not market_id:
            continue
        try:
            bid = float(_col(tup, "bid_price", "best_bid", "bid"))
            ask = float(_col(tup, "ask_price", "best_ask", "ask"))
        except (TypeError, ValueError):
            continue
        mid = (bid + ask) / 2 if (bid and ask) else bid or ask
        if mid <= 0 or mid >= 1:
            continue
        rows.append({"ts": ts, "market_id": market_id, "price": mid, "size": 1.0, "side": "buy"})
    return rows
