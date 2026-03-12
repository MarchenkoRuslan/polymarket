"""News Collector - fetches RSS feeds and stores for feature extraction."""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text
from db import SessionLocal
from services.news_collector.rss_loader import fetch_rss, filter_by_keywords

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_FEEDS = [
    "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
]

KEYWORDS = os.getenv("NEWS_KEYWORDS", "election,trump,biden,market,polymarket").split(",")


def ensure_news_table(session) -> None:
    """Create news table if not exists (SQLite and PostgreSQL compatible)."""
    from sqlalchemy import inspect
    insp = inspect(session.bind)
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


def insert_news(session, source: str, title: str, link: str, summary: str, ts: datetime) -> None:
    """Insert news item."""
    session.execute(
        text("""
            INSERT INTO news (ts, source, title, link, summary)
            VALUES (:ts, :source, :title, :link, :summary)
        """),
        {"ts": ts, "source": source, "title": title, "link": link, "summary": summary},
    )


async def main():
    """Fetch RSS, filter by keywords, store in DB."""
    logger.info("News Collector starting")
    feeds = os.getenv("RSS_FEEDS", "").split(",") if os.getenv("RSS_FEEDS") else DEFAULT_FEEDS
    session = SessionLocal()
    try:
        ensure_news_table(session)
        for url in feeds:
            url = url.strip()
            if not url:
                continue
            items = fetch_rss(url)
            filtered = filter_by_keywords(items, KEYWORDS)
            batch = filtered[:20]
            for it in batch:
                ts = it.get("published") or datetime.now(timezone.utc)
                insert_news(
                    session,
                    source=url[:50],
                    title=it.get("title", "")[:500],
                    link=it.get("link", "")[:500],
                    summary=it.get("summary", "")[:500],
                    ts=ts,
                )
            session.commit()
            logger.info("RSS %s: %d items stored", url[:40], len(batch))
    except Exception as e:
        session.rollback()
        logger.exception("%s", e)
    finally:
        session.close()
    logger.info("News Collector finished")


if __name__ == "__main__":
    asyncio.run(main())
