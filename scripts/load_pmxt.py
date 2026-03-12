"""Load historical data from PMXT archive into DB."""
import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import SessionLocal
from services.collector.pmxt_loader import (
    load_pmxt_parquet,
    trades_to_rows,
    orderbook_to_rows,
)
from services.collector.db_writer import insert_trade, insert_orderbook
from config import PMXT_ARCHIVE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_date(session, base_url: str, date_str: str, dataset: str = "Polymarket"):
    """Load one day of PMXT data."""
    trades_df = load_pmxt_parquet(base_url, dataset, date_str, "trades")
    if trades_df is not None and not trades_df.empty:
        rows = trades_to_rows(trades_df)
        for r in rows:
            insert_trade(session, r["market_id"], r["ts"], r["price"], r["size"], r["side"])
        logger.info("Loaded %d trades for %s", len(rows), date_str)

    ob_df = load_pmxt_parquet(base_url, dataset, date_str, "orderbook")
    if ob_df is not None and not ob_df.empty:
        rows = orderbook_to_rows(ob_df)
        for r in rows:
            insert_orderbook(
                session, r["market_id"], r["ts"],
                r["bid_price"], r["bid_qty"], r["ask_price"], r["ask_qty"],
            )
        logger.info("Loaded %d orderbook snapshots for %s", len(rows), date_str)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--url", default=PMXT_ARCHIVE_URL)
    args = parser.parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d")

    session = SessionLocal()
    try:
        for i in range(args.days):
            d = start + timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            load_date(session, args.url, date_str)
            session.commit()
    except Exception as e:
        session.rollback()
        logger.exception("%s", e)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
