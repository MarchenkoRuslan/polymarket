"""RSS feed loader for news signals."""
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False


def fetch_rss(url: str) -> list[dict]:
    """Fetch and parse RSS feed. Returns list of {title, link, published, summary}."""
    if not HAS_FEEDPARSER:
        logger.warning("feedparser not installed, skipping RSS")
        return []
    try:
        with httpx.Client() as client:
            resp = client.get(url, timeout=15)
            resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries[:50]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                from time import mktime
                published = datetime.utcfromtimestamp(mktime(entry.published_parsed))
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                from time import mktime
                published = datetime.utcfromtimestamp(mktime(entry.updated_parsed))
            items.append({
                "title": getattr(entry, "title", ""),
                "link": getattr(entry, "link", ""),
                "published": published,
                "summary": getattr(entry, "summary", "")[:500],
            })
        return items
    except Exception as e:
        logger.warning("RSS fetch %s: %s", url, e)
        return []


def filter_by_keywords(items: list[dict], keywords: list[str]) -> list[dict]:
    """Keep items containing any keyword (case-insensitive)."""
    if not keywords:
        return items
    kw_lower = [k.lower() for k in keywords]
    return [
        it for it in items
        if any(k in (it.get("title", "") + " " + it.get("summary", "")).lower() for k in kw_lower)
    ]
