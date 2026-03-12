"""Tests for Execution Bot orders."""
from services.execution_bot.orders import place_order, place_order_stub, cancel_order


def test_place_order_dry_run():
    """Dry run returns simulated order."""
    r = place_order("token123456", "buy", 0.5, 10.0, dry_run=True)
    assert r["status"] == "dry_run"
    assert "dryrun-" in r["order_id"]
    assert r["price"] == 0.5
    assert r["size"] == 10.0


def test_place_order_stub_backward_compat():
    """Legacy stub works (dry run)."""
    r = place_order_stub("market-abc", "buy", 0.6, 5.0)
    assert r["status"] in ("dry_run", "stub")


def test_place_order_dry_run_none_reads_env(monkeypatch):
    """dry_run=None reads from POLYMARKET_DRY_RUN env (default true)."""
    monkeypatch.delenv("POLYMARKET_DRY_RUN", raising=False)
    r = place_order("token123456", "buy", 0.5, 10.0, dry_run=None)
    assert r["status"] == "dry_run"


def test_place_order_dry_run_false_explicit(monkeypatch):
    """dry_run=False overrides env — falls through to stub (no key)."""
    monkeypatch.setenv("POLYMARKET_DRY_RUN", "true")
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    r = place_order("token123456", "buy", 0.5, 10.0, dry_run=False)
    assert r["status"] == "stub"


def test_cancel_order_dry_run_none(monkeypatch):
    """cancel_order with dry_run=None reads env."""
    monkeypatch.delenv("POLYMARKET_DRY_RUN", raising=False)
    assert cancel_order("order-123", dry_run=None) is True


def test_cancel_order_dry_run_explicit():
    """cancel_order with dry_run=True always simulates."""
    assert cancel_order("order-123", dry_run=True) is True
