"""Polymarket API client for markets, prices, orderbook, trades."""
import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _extract_list(data: Any) -> list[dict]:
    """Handle paginated or wrapped API responses."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "data" in data:
            return data["data"] if isinstance(data["data"], list) else []
        if "results" in data:
            return data["results"] if isinstance(data["results"], list) else []
    return []


class PolymarketClient:
    """Async client for Polymarket REST API."""

    def __init__(self, gamma_url: str, clob_url: str, rate_limit_delay: float = 0.1):
        self.gamma_url = gamma_url.rstrip("/")
        self.clob_url = clob_url.rstrip("/")
        self._delay = rate_limit_delay

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        await asyncio.sleep(self._delay)
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.request(method, url, **kwargs)

    async def get_markets(self, limit: int = 100, offset: int = 0, closed: bool = False) -> list[dict]:
        """Fetch markets from Gamma API. Handles pagination."""
        params = {"limit": limit, "offset": offset, "closed": str(closed).lower()}
        resp = await self._request("GET", f"{self.gamma_url}/markets", params=params)
        resp.raise_for_status()
        return _extract_list(resp.json())

    async def get_events(self, active: bool = True, closed: bool = False, limit: int = 100) -> list[dict]:
        """Fetch events (groups of markets) from Gamma API. Handles paginated response."""
        params = {"active": str(active).lower(), "closed": str(closed).lower(), "limit": limit}
        resp = await self._request("GET", f"{self.gamma_url}/events", params=params)
        resp.raise_for_status()
        return _extract_list(resp.json())

    async def get_events_paginated(
        self,
        active: bool = True,
        closed: bool = False,
        limit_per_page: int = 100,
        max_pages: int = 10,
    ) -> list[dict]:
        """Fetch all events using offset pagination."""
        all_events = []
        for offset in range(0, max_pages * limit_per_page, limit_per_page):
            params = {
                "active": str(active).lower(),
                "closed": str(closed).lower(),
                "limit": limit_per_page,
                "offset": offset,
            }
            resp = await self._request("GET", f"{self.gamma_url}/events", params=params)
            resp.raise_for_status()
            data = resp.json()
            events = _extract_list(data)
            if not events:
                break
            all_events.extend(events)
            if len(events) < limit_per_page:
                break
        return all_events

    async def get_market(self, market_id: str) -> dict | None:
        """Fetch single market by ID."""
        resp = await self._request("GET", f"{self.gamma_url}/markets/{market_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def get_prices_history(
        self, market_id: str, interval: str = "max"
    ) -> list[dict[str, Any]]:
        """Fetch price history for a market. interval: 1m, 1h, max."""
        resp = await self._request(
            "GET",
            f"{self.clob_url}/prices-history",
            params={"market": market_id, "interval": interval},
        )
        resp.raise_for_status()
        return _extract_list(resp.json())

    async def get_orderbook(self, token_id: str) -> dict | None:
        """Fetch orderbook for a token. CLOB uses token_id."""
        resp = await self._request("GET", f"{self.clob_url}/book", params={"token_id": token_id})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def get_trades(
        self, market_id: str | None = None, event_id: str | None = None, limit: int = 100
    ) -> list[dict]:
        """Fetch trades. CLOB accepts market (condition ID) or eventId."""
        if not market_id and not event_id:
            raise ValueError("Provide market_id or event_id")
        params = {"limit": limit}
        if market_id:
            params["market"] = market_id
        else:
            params["eventId"] = event_id
        resp = await self._request("GET", f"{self.clob_url}/trades", params=params)
        resp.raise_for_status()
        return _extract_list(resp.json())
