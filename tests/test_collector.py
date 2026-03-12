"""Tests for collector."""
from services.collector.db_writer import markets_from_events
from services.collector.polymarket_client import _extract_list


def test_extract_list():
    """Handle list, dict with data, dict with results."""
    assert _extract_list([1, 2]) == [1, 2]
    assert _extract_list({"data": [1, 2]}) == [1, 2]
    assert _extract_list({"results": [1]}) == [1]
    assert _extract_list({}) == []
    assert _extract_list("x") == []


def test_markets_from_events():
    """Extract markets from events."""
    events = [
        {"id": "e1", "markets": [{"id": "m1", "question": "Q1"}]},
        {"id": "e2", "market": {"id": "m2", "question": "Q2"}},
    ]
    markets = markets_from_events(events)
    assert len(markets) >= 2
    assert any(m.get("id") == "m1" or m.get("question") == "Q1" for m in markets)
