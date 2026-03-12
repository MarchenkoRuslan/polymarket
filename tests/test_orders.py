"""Tests for Execution Bot orders."""
from services.execution_bot.orders import place_order, place_order_stub


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
