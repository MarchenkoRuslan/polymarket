"""Tests for News Collector."""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from services.news_collector.rss_loader import filter_by_keywords, fetch_rss
from services.news_collector.main import (
    _source_name,
    insert_news,
)


def test_filter_by_keywords():
    """Filter items by keywords."""
    items = [
        {"title": "Election results", "summary": "..."},
        {"title": "Weather today", "summary": "..."},
    ]
    filtered = filter_by_keywords(items, ["election"])
    assert len(filtered) == 1
    assert "Election" in filtered[0]["title"]


def test_filter_empty_keywords():
    """Empty keywords returns all."""
    items = [{"title": "A"}, {"title": "B"}]
    assert len(filter_by_keywords(items, [])) == 2


def test_filter_case_insensitive():
    """Keyword matching is case-insensitive."""
    items = [{"title": "CRYPTO market surge", "summary": ""}]
    filtered = filter_by_keywords(items, ["crypto"])
    assert len(filtered) == 1


def test_filter_matches_in_summary():
    """Keywords match in summary too."""
    items = [{"title": "News update", "summary": "polymarket prediction"}]
    filtered = filter_by_keywords(items, ["polymarket"])
    assert len(filtered) == 1


def test_filter_no_match():
    """No matches returns empty."""
    items = [{"title": "Unrelated article", "summary": "Nothing here"}]
    filtered = filter_by_keywords(items, ["bitcoin", "election"])
    assert len(filtered) == 0


def test_source_name_coindesk():
    assert _source_name("https://www.coindesk.com/rss") == "CoinDesk"


def test_source_name_google_news():
    assert _source_name("https://news.google.com/rss/search?q=polymarket") == "Google News"


def test_source_name_reuters():
    assert _source_name("https://feeds.reuters.com/reuters/topNews") == "Reuters"


def test_source_name_nytimes():
    assert _source_name("https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml") == "NY Times"


def test_source_name_cointelegraph():
    assert _source_name("https://cointelegraph.com/rss") == "CoinTelegraph"


def test_source_name_unknown():
    name = _source_name("https://example.com/feed")
    assert "example.com" in name


def test_fetch_rss_no_feedparser():
    """fetch_rss gracefully handles missing feedparser."""
    with patch("services.news_collector.rss_loader.HAS_FEEDPARSER", False):
        result = fetch_rss("https://example.com/rss")
        assert result == []


def test_fetch_rss_network_error():
    """fetch_rss returns empty list on network error."""
    with patch("services.news_collector.rss_loader.httpx") as mock_httpx:
        mock_httpx.Client.return_value.__enter__ = MagicMock(side_effect=Exception("timeout"))
        mock_httpx.Client.return_value.__exit__ = MagicMock(return_value=False)
        result = fetch_rss("https://example.com/rss")
        assert result == []


class TestInsertNews:
    """Tests for insert_news duplicate detection."""

    def _make_session(self):
        session = MagicMock()
        session.execute.return_value.fetchone.return_value = None
        return session

    def test_insert_new_item(self):
        session = self._make_session()
        ts = datetime.now(timezone.utc)
        result = insert_news(session, "Test", "Title", "https://example.com", "Summary", ts)
        assert result is True

    def test_skip_duplicate_link(self):
        session = self._make_session()
        session.execute.return_value.fetchone.return_value = (1,)
        ts = datetime.now(timezone.utc)
        result = insert_news(session, "Test", "Title", "https://example.com", "Summary", ts)
        assert result is False

    def test_dedup_by_title_when_no_link(self):
        session = self._make_session()
        session.execute.return_value.fetchone.return_value = (1,)
        ts = datetime.now(timezone.utc)
        result = insert_news(session, "Test", "Title", "", "Summary", ts)
        assert result is False

    def test_insert_when_no_link_no_match(self):
        session = self._make_session()
        ts = datetime.now(timezone.utc)
        result = insert_news(session, "Test", "Title", "", "Summary", ts)
        assert result is True
