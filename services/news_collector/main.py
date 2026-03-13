"""News Collector - fetches RSS feeds and stores for feature extraction."""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import inspect as sa_inspect, text
from db import SessionLocal
from services.news_collector.rss_loader import fetch_rss, filter_by_keywords

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_FEEDS = [
    "https://news.google.com/rss/search?q=polymarket+OR+prediction+market&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=crypto+market+prediction&hl=en-US&gl=US&ceid=US:en",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://feeds.reuters.com/reuters/topNews",
]

KEYWORDS = os.getenv(
    "NEWS_KEYWORDS",
    "election,trump,biden,polymarket,prediction market,crypto,betting,odds,"
    "forecast,poll,probability,wager,futures,congress,senate,president,"
    "democrat,republican,vote,market,trade,economy",
).split(",")


def ensure_news_table(session) -> None:
    """Create news table if not exists (SQLite and PostgreSQL compatible)."""
    insp = sa_inspect(session.bind)
    if "news" not in insp.get_table_names():
        dialect = session.bind.dialect.name
        if dialect == "sqlite":
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT,
                    link TEXT,
                    summary TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """))
        else:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS news (
                    id SERIAL PRIMARY KEY,
                    ts TIMESTAMP NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT,
                    link TEXT,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_news_ts ON news (ts)"))
        session.commit()


def insert_news(session, source: str, title: str, link: str, summary: str, ts: datetime) -> bool:
    """Insert news item if link is not already stored. Returns True if inserted."""
    if link:
        exists = session.execute(
            text("SELECT 1 FROM news WHERE link = :link LIMIT 1"),
            {"link": link},
        ).fetchone()
        if exists:
            return False
    session.execute(
        text("""
            INSERT INTO news (ts, source, title, link, summary)
            VALUES (:ts, :source, :title, :link, :summary)
        """),
        {"ts": ts, "source": source, "title": title, "link": link, "summary": summary},
    )
    return True


def _source_name(url: str) -> str:
    """Extract a human-readable source name from a feed URL."""
    url_lower = url.lower()
    if "coindesk" in url_lower:
        return "CoinDesk"
    if "cointelegraph" in url_lower:
        return "CoinTelegraph"
    if "reuters" in url_lower:
        return "Reuters"
    if "nytimes" in url_lower:
        return "NY Times"
    if "news.google" in url_lower:
        return "Google News"
    if "polymarket" in url_lower:
        return "Polymarket"
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or url[:40]
    except Exception:
        return url[:40]


async def main():
    """Fetch RSS, filter by keywords, store in DB."""
    logger.info("News Collector starting")
    feeds = os.getenv("RSS_FEEDS", "").split(",") if os.getenv("RSS_FEEDS") else DEFAULT_FEEDS
    session = SessionLocal()
    total_stored = 0
    try:
        ensure_news_table(session)
        for url in feeds:
            url = url.strip()
            if not url:
                continue
            source = _source_name(url)
            items = fetch_rss(url)
            filtered = filter_by_keywords(items, KEYWORDS)
            batch = filtered[:30]
            stored = 0
            for it in batch:
                ts = it.get("published") or datetime.now(timezone.utc)
                inserted = insert_news(
                    session,
                    source=source,
                    title=it.get("title", "")[:500],
                    link=it.get("link", "")[:500],
                    summary=it.get("summary", "")[:500],
                    ts=ts,
                )
                if inserted:
                    stored += 1
            session.commit()
            total_stored += stored
            logger.info("RSS %s: %d/%d items stored (new)", source, stored, len(batch))
    except Exception as e:
        session.rollback()
        logger.exception("%s", e)
    finally:
        session.close()
    logger.info("News Collector finished: %d total new items", total_stored)


if __name__ == "__main__":
    asyncio.run(main())
