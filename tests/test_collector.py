"""Tests for collector."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.collector.db_writer import markets_from_events
from services.collector.polymarket_client import PolymarketClient, _extract_list


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


@pytest.mark.asyncio
async def test_get_prices_history_extracts_history_key():
    """get_prices_history returns data from 'history' key in response."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"history": [{"t": 1704067200000, "p": 0.55}, {"t": 1704070800000, "p": 0.56}]}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.get_prices_history("token123", interval="max")
    assert len(result) == 2
    assert result[0] == {"t": 1704067200000, "p": 0.55}
    assert result[1]["p"] == 0.56


@pytest.mark.asyncio
async def test_get_prices_history_empty_history():
    """get_prices_history returns [] when history is empty."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"history": []}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.get_prices_history("token123")
    assert result == []
