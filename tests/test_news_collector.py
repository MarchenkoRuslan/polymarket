"""Tests for News Collector."""
from services.news_collector.rss_loader import filter_by_keywords


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
