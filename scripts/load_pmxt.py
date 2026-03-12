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
    load_pmxt_parquet_hourly,
    trades_to_rows,
    orderbook_to_rows,
    orderbook_to_trade_rows,
)
from services.collector.db_writer import insert_trade, insert_orderbook
from config import PMXT_ARCHIVE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_date(session, base_url: str, date_str: str, dataset: str = "Polymarket"):
    """Load one day of PMXT data (legacy daily format)."""
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


def load_hour(session, base_url: str, date_str: str, hour: int):
    """Load one hour of PMXT data (new hourly format). Orderbook + synthetic trades from mid-price."""
    ob_df = load_pmxt_parquet_hourly(base_url, "orderbook", date_str, hour)
    if ob_df is not None and not ob_df.empty:
        rows = orderbook_to_rows(ob_df)
        for r in rows:
            insert_orderbook(
                session, r["market_id"], r["ts"],
                r["bid_price"], r["bid_qty"], r["ask_price"], r["ask_qty"],
            )
        trade_rows = orderbook_to_trade_rows(ob_df)
        for r in trade_rows:
            insert_trade(session, r["market_id"], r["ts"], r["price"], r["size"], r["side"])
        logger.info("Loaded %d orderbook + %d trades for %sT%02d", len(rows), len(trade_rows), date_str, hour)
        return len(rows) + len(trade_rows)

    trades_df = load_pmxt_parquet_hourly(base_url, "trades", date_str, hour)
    if trades_df is not None and not trades_df.empty:
        rows = trades_to_rows(trades_df)
        for r in rows:
            insert_trade(session, r["market_id"], r["ts"], r["price"], r["size"], r["side"])
        logger.info("Loaded %d trades for %sT%02d", len(rows), date_str, hour)
        return len(rows)

    return 0


def main():
    parser = argparse.ArgumentParser(description="Load historical PMXT data into DB")
    parser.add_argument("--start", default="2026-03-10", help="Start date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=0, help="Legacy: load N days (daily format)")
    parser.add_argument("--hours", type=int, default=6, help="Load N hours (hourly format, default 6)")
    parser.add_argument("--url", default=PMXT_ARCHIVE_URL)
    parser.add_argument("--legacy", action="store_true", help="Use legacy daily format instead of hourly")
    args = parser.parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d")

    session = SessionLocal()
    try:
        if args.legacy or args.days > 0:
            days = args.days or 7
            for i in range(days):
                d = start + timedelta(days=i)
                date_str = d.strftime("%Y-%m-%d")
                load_date(session, args.url, date_str)
                session.commit()
        else:
            total = 0
            for h in range(args.hours):
                d = start + timedelta(hours=h)
                date_str = d.strftime("%Y-%m-%d")
                hour = d.hour
                n = load_hour(session, args.url, date_str, hour)
                total += n
                if (h + 1) % 3 == 0:
                    session.commit()
            session.commit()
            logger.info("Total: %d records", total)
            if total == 0:
                logger.warning(
                    "PMXT archive returned no data. Try: .\\run.ps1 collect && .\\run.ps1 warmup"
                )
    except Exception as e:
        session.rollback()
        logger.exception("%s", e)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
