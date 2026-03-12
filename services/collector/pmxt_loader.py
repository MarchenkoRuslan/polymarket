"""Load historical data from PMXT Parquet archive."""
import io
import logging
from datetime import datetime
from urllib.parse import urljoin

import httpx
import pandas as pd

logger = logging.getLogger(__name__)


def load_pmxt_parquet(
    base_url: str,
    dataset: str,
    date_str: str,
    table: str,
) -> pd.DataFrame | None:
    """
    Load Parquet file from PMXT archive.
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


def trades_to_rows(df: pd.DataFrame, market_id_col: str = "market") -> list[dict]:
    """Convert PMXT trades DataFrame to list of dicts for DB insert."""
    if df is None or df.empty:
        return []
    rows = []
    for _, row in df.iterrows():
        ts = row.get("timestamp") or row.get("ts") or row.get("t")
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        elif isinstance(ts, (int, float)):
            ts = datetime.utcfromtimestamp(ts)
        market_id = str(row.get(market_id_col, row.get("market_id", "")))
        price = float(row.get("price", 0))
        size = float(row.get("size", row.get("volume", 0)))
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
        ts = row.get("timestamp") or row.get("ts") or row.get("t")
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        elif isinstance(ts, (int, float)):
            ts = datetime.utcfromtimestamp(ts)
        market_id = str(row.get(market_id_col, row.get("market_id", "")))
        bid_price = float(row.get("bid_price", row.get("best_bid", 0)))
        bid_qty = float(row.get("bid_qty", row.get("bid_size", 0)))
        ask_price = float(row.get("ask_price", row.get("best_ask", 0)))
        ask_qty = float(row.get("ask_qty", row.get("ask_size", 0)))
        rows.append({
            "ts": ts, "market_id": market_id,
            "bid_price": bid_price, "bid_qty": bid_qty,
            "ask_price": ask_price, "ask_qty": ask_qty,
        })
    return rows
