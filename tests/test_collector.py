"""Tests for collector."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.collector.db_writer import markets_from_events
from services.collector.main import _parse_outcome_prices
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


class TestParseOutcomePrices:
    """Tests for _parse_outcome_prices handling various Gamma API formats."""

    def test_none_returns_none(self):
        assert _parse_outcome_prices(None) is None

    def test_float_in_range(self):
        assert _parse_outcome_prices(0.55) == 0.55

    def test_float_out_of_range(self):
        assert _parse_outcome_prices(0.0) is None
        assert _parse_outcome_prices(1.0) is None
        assert _parse_outcome_prices(1.5) is None

    def test_int_in_range(self):
        assert _parse_outcome_prices(0) is None

    def test_string_simple(self):
        assert _parse_outcome_prices("0.65") == 0.65

    def test_string_comma_separated(self):
        assert _parse_outcome_prices("0.65,0.35") == 0.65

    def test_list_of_strings(self):
        result = _parse_outcome_prices(["0.145", "0.855"])
        assert result == 0.145

    def test_list_of_floats(self):
        result = _parse_outcome_prices([0.3, 0.7])
        assert result == 0.3

    def test_json_string_list(self):
        result = _parse_outcome_prices('["0.145", "0.855"]')
        assert result == 0.145

    def test_empty_list(self):
        assert _parse_outcome_prices([]) is None

    def test_empty_string(self):
        assert _parse_outcome_prices("") is None

    def test_invalid_string(self):
        assert _parse_outcome_prices("not_a_number") is None

    def test_list_with_invalid_items(self):
        assert _parse_outcome_prices(["abc", "def"]) is None

    def test_list_with_out_of_range_first(self):
        result = _parse_outcome_prices(["1.5", "0.5"])
        assert result == 0.5


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
