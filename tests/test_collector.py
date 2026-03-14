"""Tests for collector."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.collector.db_writer import markets_from_events
from services.collector.main import (
    _collect_orderbook,
    _extract_market_id,
    _parse_clob_token_ids,
    _parse_outcome_prices,
)
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


class TestParseClobTokenIds:
    """Tests for _parse_clob_token_ids handling Gamma API clobTokenIds field."""

    def test_none_returns_empty(self):
        assert _parse_clob_token_ids(None) == []

    def test_empty_string_returns_empty(self):
        assert _parse_clob_token_ids("") == []

    def test_list_of_strings(self):
        result = _parse_clob_token_ids(["token1", "token2"])
        assert result == ["token1", "token2"]

    def test_json_string_list(self):
        result = _parse_clob_token_ids('["111222333", "444555666"]')
        assert result == ["111222333", "444555666"]

    def test_json_string_single(self):
        result = _parse_clob_token_ids('["111222333"]')
        assert result == ["111222333"]

    def test_plain_string(self):
        result = _parse_clob_token_ids("111222333")
        assert result == ["111222333"]

    def test_empty_list(self):
        assert _parse_clob_token_ids([]) == []

    def test_real_gamma_format(self):
        raw = '["93592949212798121127213117304912625505836768562433217537850469496310204567695", "3074539347152748632858978545166555332546941892131779352477699494423276162345"]'
        result = _parse_clob_token_ids(raw)
        assert len(result) == 2
        assert result[0].startswith("935929")

    def test_invalid_json(self):
        result = _parse_clob_token_ids("[invalid")
        assert result == ["[invalid"]


class TestExtractMarketId:
    """Tests for _extract_market_id."""

    def test_uses_id_first(self):
        assert _extract_market_id({"id": "123", "conditionId": "0xabc"}) == "123"

    def test_falls_back_to_condition_id(self):
        assert _extract_market_id({"conditionId": "0xabc"}) == "0xabc"

    def test_falls_back_to_condition_id_underscore(self):
        assert _extract_market_id({"condition_id": "0xdef"}) == "0xdef"

    def test_empty_dict(self):
        assert _extract_market_id({}) == ""

    def test_list_market_id(self):
        assert _extract_market_id({"id": ["m1", "m2"]}) == "m1"

    def test_none_values(self):
        assert _extract_market_id({"id": None, "conditionId": None}) == ""


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


# -- PolymarketClient.get_orderbook tests --


@pytest.mark.asyncio
async def test_get_orderbook_returns_book():
    """get_orderbook returns parsed JSON from CLOB /book."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "bids": [{"price": "0.45", "size": "100"}],
        "asks": [{"price": "0.55", "size": "200"}],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.get_orderbook("token123")
    assert result is not None
    assert "bids" in result
    assert "asks" in result
    assert result["bids"][0]["price"] == "0.45"


@pytest.mark.asyncio
async def test_get_orderbook_returns_none_on_404():
    """get_orderbook returns None when token not found."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.get_orderbook("unknown_token")
    assert result is None


# -- _collect_orderbook tests --


@pytest.mark.asyncio
async def test_collect_orderbook_clob_primary():
    """_collect_orderbook uses CLOB data when available."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)

    clob_book = {
        "bids": [{"price": "0.42", "size": "150"}],
        "asks": [{"price": "0.58", "size": "250"}],
    }
    with patch.object(client, "get_orderbook", new_callable=AsyncMock, return_value=clob_book):
        session = MagicMock()
        market = {"bestBid": "0.40", "bestAsk": "0.60"}
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)
        result = await _collect_orderbook(client, session, market, "m1", "token1", now)

    assert result is True
    session.execute.assert_called_once()
    call_params = session.execute.call_args
    params = call_params[1] if call_params[1] else call_params[0][1]
    assert params["bid_price"] == 0.42
    assert params["ask_price"] == 0.58
    assert params["bid_qty"] == 150.0
    assert params["ask_qty"] == 250.0


@pytest.mark.asyncio
async def test_collect_orderbook_gamma_fallback():
    """_collect_orderbook falls back to Gamma bestBid/bestAsk when CLOB fails."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)

    with patch.object(client, "get_orderbook", new_callable=AsyncMock, side_effect=Exception("CLOB down")):
        session = MagicMock()
        market = {"bestBid": "0.40", "bestAsk": "0.60"}
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)
        result = await _collect_orderbook(client, session, market, "m1", "token1", now)

    assert result is True
    session.execute.assert_called_once()
    call_params = session.execute.call_args
    params = call_params[1] if call_params[1] else call_params[0][1]
    assert params["bid_price"] == 0.40
    assert params["ask_price"] == 0.60


@pytest.mark.asyncio
async def test_collect_orderbook_gamma_fallback_on_empty_clob():
    """_collect_orderbook falls back to Gamma when CLOB returns empty bids/asks."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)
    empty_book = {"bids": [], "asks": []}

    with patch.object(client, "get_orderbook", new_callable=AsyncMock, return_value=empty_book):
        session = MagicMock()
        market = {"bestBid": "0.35", "bestAsk": "0.65"}
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)
        result = await _collect_orderbook(client, session, market, "m1", "token1", now)

    assert result is True
    session.execute.assert_called_once()
    call_params = session.execute.call_args
    params = call_params[1] if call_params[1] else call_params[0][1]
    assert params["bid_price"] == 0.35
    assert params["ask_price"] == 0.65


@pytest.mark.asyncio
async def test_collect_orderbook_no_data_anywhere():
    """_collect_orderbook returns False when neither CLOB nor Gamma have data."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)

    with patch.object(client, "get_orderbook", new_callable=AsyncMock, return_value=None):
        session = MagicMock()
        market = {}
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)
        result = await _collect_orderbook(client, session, market, "m1", "token1", now)

    assert result is False
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_collect_orderbook_invalid_gamma_prices():
    """_collect_orderbook returns False when Gamma prices are out of range."""
    client = PolymarketClient("https://gamma.test", "https://clob.test", rate_limit_delay=0)

    with patch.object(client, "get_orderbook", new_callable=AsyncMock, return_value=None):
        session = MagicMock()
        market = {"bestBid": "0.0", "bestAsk": "1.0"}
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)
        result = await _collect_orderbook(client, session, market, "m1", "token1", now)

    assert result is False
    session.execute.assert_not_called()


# -- collect_from_api flow and COLLECT_MARKETS_LIMIT tests --


@pytest.mark.asyncio
async def test_collect_from_api_processes_all_liquid_markets():
    """collect_from_api processes all liquid markets when COLLECT_MARKETS_LIMIT=0."""
    from services.collector.main import collect_from_api

    events = [
        {
            "id": "e1",
            "markets": [
                {"id": f"m{i}", "question": f"Q{i}", "clobTokenIds": [f"tok{i}"], "volume": "5000"}
                for i in range(5)
            ],
        }
    ]

    mock_client = AsyncMock()
    mock_client.get_events_paginated = AsyncMock(return_value=events)
    mock_client.get_prices_history = AsyncMock(return_value=[])
    mock_client.get_orderbook = AsyncMock(return_value=None)
    mock_client.close = AsyncMock()

    mock_session = MagicMock()
    mock_session.execute = MagicMock()
    mock_session.commit = MagicMock()

    with (
        patch("services.collector.main.PolymarketClient", return_value=mock_client),
        patch("services.collector.main.SessionLocal", return_value=mock_session),
        patch("services.collector.main.COLLECT_MARKETS_LIMIT", 0),
        patch("services.collector.main._init_clob_client", return_value=None),
    ):
        await collect_from_api()

    assert mock_client.get_orderbook.call_count == 5


@pytest.mark.asyncio
async def test_collect_from_api_respects_markets_limit():
    """collect_from_api only processes COLLECT_MARKETS_LIMIT markets when set."""
    from services.collector.main import collect_from_api

    events = [
        {
            "id": "e1",
            "markets": [
                {"id": f"m{i}", "question": f"Q{i}", "clobTokenIds": [f"tok{i}"], "volume": "5000"}
                for i in range(10)
            ],
        }
    ]

    mock_client = AsyncMock()
    mock_client.get_events_paginated = AsyncMock(return_value=events)
    mock_client.get_prices_history = AsyncMock(return_value=[])
    mock_client.get_orderbook = AsyncMock(return_value=None)
    mock_client.close = AsyncMock()

    mock_session = MagicMock()
    mock_session.execute = MagicMock()
    mock_session.commit = MagicMock()

    with (
        patch("services.collector.main.PolymarketClient", return_value=mock_client),
        patch("services.collector.main.SessionLocal", return_value=mock_session),
        patch("services.collector.main.COLLECT_MARKETS_LIMIT", 3),
        patch("services.collector.main._init_clob_client", return_value=None),
    ):
        await collect_from_api()

    assert mock_client.get_orderbook.call_count == 3


@pytest.mark.asyncio
async def test_collect_from_api_inserts_fee_rates():
    """collect_from_api calls upsert_fee_rate for each processed market."""
    from services.collector.main import collect_from_api

    events = [
        {
            "id": "e1",
            "markets": [
                {"id": "m1", "question": "Q1", "clobTokenIds": ["tok1"], "volume": "5000"},
                {"id": "m2", "question": "Q2", "clobTokenIds": ["tok2"], "volume": "5000"},
            ],
        }
    ]

    mock_client = AsyncMock()
    mock_client.get_events_paginated = AsyncMock(return_value=events)
    mock_client.get_prices_history = AsyncMock(return_value=[])
    mock_client.get_orderbook = AsyncMock(return_value=None)
    mock_client.close = AsyncMock()

    mock_session = MagicMock()
    mock_session.execute = MagicMock()
    mock_session.commit = MagicMock()

    with (
        patch("services.collector.main.PolymarketClient", return_value=mock_client),
        patch("services.collector.main.SessionLocal", return_value=mock_session),
        patch("services.collector.main.COLLECT_MARKETS_LIMIT", 0),
        patch("services.collector.main.upsert_fee_rate") as mock_fee,
        patch("services.collector.main._init_clob_client", return_value=None),
    ):
        await collect_from_api()

    assert mock_fee.call_count == 2
    mock_fee.assert_any_call(mock_session, "tok1", 30)
    mock_fee.assert_any_call(mock_session, "tok2", 30)
