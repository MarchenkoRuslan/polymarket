"""Tests for config/settings.py — _apply_sslmode and DATABASE_URL construction."""
from config.settings import _apply_sslmode


class TestApplySslmode:
    def test_adds_require_to_postgresql_url(self):
        url = "postgresql://user:pass@host:5432/db"
        result = _apply_sslmode(url, "require")
        assert "sslmode=require" in result
        assert result.startswith("postgresql://")

    def test_adds_disable_to_postgresql_url(self):
        url = "postgresql://user:pass@host:5432/db"
        result = _apply_sslmode(url, "disable")
        assert "sslmode=disable" in result

    def test_skips_sqlite_url(self):
        url = "sqlite:///test.db"
        result = _apply_sslmode(url, "require")
        assert result == url
        assert "sslmode" not in result

    def test_skips_when_sslmode_already_in_url(self):
        url = "postgresql://user:pass@host:5432/db?sslmode=verify-full"
        result = _apply_sslmode(url, "require")
        assert result == url
        assert "sslmode=require" not in result
        assert "sslmode=verify-full" in result

    def test_preserves_existing_query_params(self):
        url = "postgresql://user:pass@host:5432/db?connect_timeout=10"
        result = _apply_sslmode(url, "require")
        assert "connect_timeout=10" in result
        assert "sslmode=require" in result

    def test_empty_url_returns_empty(self):
        assert _apply_sslmode("", "require") == ""

    def test_none_url_returns_none(self):
        assert _apply_sslmode(None, "require") is None

    def test_empty_sslmode_skips(self):
        url = "postgresql://user:pass@host:5432/db"
        result = _apply_sslmode(url, "")
        assert result == url
        assert "sslmode" not in result

    def test_none_sslmode_skips(self):
        url = "postgresql://user:pass@host:5432/db"
        result = _apply_sslmode(url, None)
        assert result == url
        assert "sslmode" not in result

    def test_postgres_colon_slash_slash_not_matched(self):
        """URLs with postgres:// (without 'ql') should be fixed before calling this."""
        url = "postgres://user:pass@host:5432/db"
        result = _apply_sslmode(url, "require")
        assert result == url

    def test_verify_ca_mode(self):
        url = "postgresql://user:pass@host:5432/db"
        result = _apply_sslmode(url, "verify-ca")
        assert "sslmode=verify-ca" in result

    def test_prefer_mode(self):
        url = "postgresql://user:pass@host:5432/db"
        result = _apply_sslmode(url, "prefer")
        assert "sslmode=prefer" in result
