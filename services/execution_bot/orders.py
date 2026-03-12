"""Order execution via Polymarket CLOB API (py-clob-client) with dry-run support."""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# token_id required for real orders; market condition_id is not enough
HAS_PY_CLOB = False
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, OrderType
    from py_clob_client.order_builder.constants import BUY, SELL

    HAS_PY_CLOB = True
except ImportError:
    pass


def _get_client() -> "ClobClient | None":
    """Create authenticated ClobClient if credentials exist."""
    if not HAS_PY_CLOB:
        return None
    key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not key:
        return None
    try:
        client = ClobClient(
            "https://clob.polymarket.com",
            key=key,
            chain_id=137,
        )
        creds = client.create_or_derive_api_creds()
        if creds:
            client.set_api_creds(creds)
        return client
    except Exception as e:
        logger.warning("ClobClient init failed: %s", e)
        return None


def place_order(
    token_id: str,
    side: str,
    price: float,
    size: float,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Place order via py-clob-client or stub.
    token_id: outcome token ID (from market clobTokenIds).
    side: 'buy' or 'sell'.
    dry_run: if True, simulate without posting.
    """
    dry_run = dry_run or os.getenv("POLYMARKET_DRY_RUN", "true").lower() == "true"

    if dry_run:
        logger.info("DRY RUN: would place %s %.2f @ %.4f token=%s", side, size, price, token_id[:16])
        return {
            "order_id": f"dryrun-{token_id[:8]}",
            "status": "dry_run",
            "token_id": token_id,
            "side": side,
            "price": price,
            "size": size,
        }

    client = _get_client()
    if not client:
        logger.warning("No ClobClient (missing key or py-clob-client), using stub")
        return {
            "order_id": f"stub-{token_id[:8]}",
            "status": "stub",
            "token_id": token_id,
            "side": side,
            "price": price,
            "size": size,
        }

    side_val = BUY if str(side).lower() == "buy" else SELL
    try:
        order_args = OrderArgs(
            token_id=token_id,
            price=round(price, 2),
            size=round(size, 2),
            side=side_val,
        )
        signed = client.create_order(order_args)
        resp = client.post_order(signed, OrderType.GTC)
        return {
            "order_id": resp.get("orderID", resp.get("order_id", "")),
            "status": resp.get("status", "submitted"),
            "token_id": token_id,
            "side": side,
            "price": price,
            "size": size,
        }
    except Exception as e:
        logger.exception("Order failed: %s", e)
        return {
            "order_id": "",
            "status": "error",
            "error": str(e),
            "token_id": token_id,
            "side": side,
            "price": price,
            "size": size,
        }


def place_order_stub(market_id: str, side: str, price: float, size: float) -> dict[str, Any]:
    """Legacy stub: uses market_id as token_id (may fail for real orders)."""
    return place_order(token_id=market_id, side=side, price=price, size=size, dry_run=True)


def cancel_order(order_id: str, dry_run: bool = True) -> bool:
    """Cancel order. dry_run: simulate only."""
    if dry_run or os.getenv("POLYMARKET_DRY_RUN", "true").lower() == "true":
        logger.info("DRY RUN: would cancel order %s", order_id)
        return True
    client = _get_client()
    if not client:
        return False
    try:
        client.cancel(order_id)
        return True
    except Exception as e:
        logger.exception("Cancel failed: %s", e)
        return False


def cancel_order_stub(order_id: str) -> bool:
    """Legacy stub."""
    return cancel_order(order_id, dry_run=True)
