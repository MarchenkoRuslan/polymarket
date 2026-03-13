"""Tests for PMXT loader parsing utilities."""
from datetime import datetime, timezone

from services.collector.pmxt_loader import _parse_ts, _get_ts_field, _get_market_id


class TestParseTs:
    def test_none_returns_none(self):
        assert _parse_ts(None) is None

    def test_unix_seconds(self):
        result = _parse_ts(1700000000)
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_unix_millis(self):
        result = _parse_ts(1700000000000)
        assert isinstance(result, datetime)
        assert result.year >= 2023

    def test_iso_string(self):
        result = _parse_ts("2024-01-01T12:00:00Z")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_iso_string_no_tz(self):
        result = _parse_ts("2024-01-01T12:00:00")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_invalid_string_returns_none(self):
        assert _parse_ts("not-a-date") is None

    def test_nan_returns_none(self):
        assert _parse_ts(float("nan")) is None

    def test_datetime_naive_gets_utc(self):
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = _parse_ts(dt)
        assert result.tzinfo == timezone.utc

    def test_datetime_aware_preserved(self):
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = _parse_ts(dt)
        assert result == dt


class TestGetTsField:
    def test_finds_timestamp(self):
        row = {"timestamp": 123, "other": "x"}
        assert _get_ts_field(row) == 123

    def test_finds_ts(self):
        row = {"ts": 456}
        assert _get_ts_field(row) == 456

    def test_finds_t(self):
        row = {"t": 789}
        assert _get_ts_field(row) == 789

    def test_returns_none_when_missing(self):
        row = {"price": 0.5}
        assert _get_ts_field(row) is None


class TestGetMarketId:
    def test_default_col(self):
        row = {"market": "abc"}
        assert _get_market_id(row) == "abc"

    def test_fallback_cols(self):
        row = {"condition_id": "xyz"}
        assert _get_market_id(row) == "xyz"

    def test_empty_returns_empty(self):
        row = {"price": 0.5}
        assert _get_market_id(row) == ""
