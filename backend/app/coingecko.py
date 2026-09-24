"""Thin async client for the CoinGecko REST API with rate limiting and retries."""

import asyncio
import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)


class CoinGeckoError(Exception):
    """Raised when CoinGecko could not be reached or kept returning errors."""


class RateLimiter:
    """Spaces request starts evenly (60 / per_minute seconds apart) across all
    concurrent callers, which keeps us under CoinGecko's per-minute quota."""

    def __init__(self, per_minute: int):
        self._interval = 60.0 / per_minute
        self._lock = asyncio.Lock()
        self._next_slot = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._next_slot - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_slot = max(now, self._next_slot) + self._interval


class CoinGeckoClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        rate_limit_per_min: int = 25,
        timeout: float = 20.0,
    ):
        headers = {"Accept": "application/json"}
        if api_key:
            headers["x-cg-demo-api-key"] = api_key
        self._http = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout)
        self._limiter = RateLimiter(rate_limit_per_min)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_markets(self, page: int, per_page: int = 250) -> list[dict[str, Any]]:
        """One page of ``/coins/markets`` ordered by market cap (max 250 rows)."""
        return await self._get(
            "/coins/markets",
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
            },
        )

    async def get_coin(self, coin_id: str) -> dict[str, Any]:
        """``/coins/{id}`` with every optional section switched off except market data."""
        return await self._get(
            f"/coins/{coin_id}",
            {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
        )

    async def _get(self, path: str, params: dict[str, Any], retries: int = 3) -> Any:
        for attempt in range(retries + 1):
            await self._limiter.acquire()
            try:
                response = await self._http.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == retries:
                    raise CoinGeckoError(f"Could not reach CoinGecko: {exc}") from exc
                await asyncio.sleep(_backoff(attempt))
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == retries:
                    raise CoinGeckoError(f"CoinGecko returned HTTP {response.status_code} for {path}")
                delay = _retry_after(response) or _backoff(attempt)
                log.warning("CoinGecko %s on %s, retrying in %.1fs", response.status_code, path, delay)
                await asyncio.sleep(delay)
                continue

            if response.status_code >= 400:
                raise CoinGeckoError(f"CoinGecko returned HTTP {response.status_code} for {path}")
            return response.json()

        raise CoinGeckoError(f"Gave up on {path}")  # unreachable, keeps type checkers happy


def _backoff(attempt: int) -> float:
    return 2.0 * (2**attempt)  # 2s, 4s, 8s


def _retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("Retry-After")
    try:
        return float(header) if header else None
    except ValueError:  # HTTP-date form; fall back to exponential backoff
        return None
