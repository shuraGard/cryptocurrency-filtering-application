"""Orchestrates fetching, caching and filtering. This is the only module that
knows both the CoinGecko client and the filter rules."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .cache import TTLCache
from .coingecko import CoinGeckoClient
from .config import Settings
from .filters import FilterCriteria, passes_detail_filters, passes_market_filters
from .schemas import CoinDetails, MarketCoin, Project, ProjectsResponse, ScanMeta

log = logging.getLogger(__name__)

_MARKETS_KEY = "markets"


@dataclass(frozen=True)
class MarketSnapshot:
    coins: list[MarketCoin]
    fetched_at: datetime


class ProjectService:
    def __init__(self, client: CoinGeckoClient, settings: Settings):
        self._client = client
        self._settings = settings
        self._markets: TTLCache[str, MarketSnapshot] = TTLCache(settings.markets_cache_ttl_seconds)
        self._details: TTLCache[str, CoinDetails] = TTLCache(settings.details_cache_ttl_seconds)
        self._refresh_lock = asyncio.Lock()
        # Detail lookups currently in progress, shared by all requests (see _details_task).
        self._inflight: dict[str, asyncio.Task[CoinDetails]] = {}

    async def get_projects(self, criteria: FilterCriteria) -> ProjectsResponse:
        snapshot = await self._load_markets()

        candidates = [coin for coin in snapshot.coins if passes_market_filters(coin, criteria)]
        candidates.sort(key=lambda coin: coin.market_cap or 0, reverse=True)
        truncated = len(candidates) > self._settings.max_detail_fetches
        candidates = candidates[: self._settings.max_detail_fetches]

        details, failures = await self._load_details([coin.id for coin in candidates])
        projects = [Project.merge(coin, details[coin.id]) for coin in candidates if coin.id in details]
        items = [project for project in projects if passes_detail_filters(project, criteria)]

        return ProjectsResponse(
            count=len(items),
            items=items,
            meta=ScanMeta(
                fetched_at=snapshot.fetched_at,
                scanned_coins=len(snapshot.coins),
                candidates=len(candidates),
                candidates_truncated=truncated,
                detail_failures=failures,
            ),
        )

    async def warm_up(self) -> None:
        """Populate the caches in the background so the first real request is fast."""
        try:
            await self.get_projects(FilterCriteria())
            log.info("Warm-up finished")
        except Exception:  # noqa: BLE001 - warm-up must never crash the app
            log.exception("Warm-up failed; the first request will retry")

    async def _load_markets(self) -> MarketSnapshot:
        cached = self._markets.get(_MARKETS_KEY)
        if cached is not None:
            return cached
        # Single flight: concurrent callers wait for one refresh instead of all hitting CoinGecko.
        async with self._refresh_lock:
            cached = self._markets.get(_MARKETS_KEY)
            if cached is not None:
                return cached
            pages = await asyncio.gather(
                *(self._client.get_markets(page=page) for page in range(1, self._settings.market_pages + 1))
            )
            coins = [MarketCoin.model_validate(row) for page in pages for row in page]
            snapshot = MarketSnapshot(coins=coins, fetched_at=datetime.now(timezone.utc))
            self._markets.set(_MARKETS_KEY, snapshot)
            log.info("Fetched %d coins from CoinGecko markets", len(coins))
            return snapshot

    async def _load_details(self, coin_ids: list[str]) -> tuple[dict[str, CoinDetails], int]:
        """Return details for the given ids (from cache where possible) and the
        number of ids whose lookup failed."""
        found: dict[str, CoinDetails] = {}
        missing: list[str] = []
        for coin_id in coin_ids:
            cached = self._details.get(coin_id)
            if cached is not None:
                found[coin_id] = cached
            else:
                missing.append(coin_id)

        # The rate limiter inside the client spaces the calls out. shield() keeps a
        # shared lookup alive if this particular request is cancelled.
        results = await asyncio.gather(
            *(asyncio.shield(self._details_task(coin_id)) for coin_id in missing),
            return_exceptions=True,
        )

        failures = 0
        for coin_id, result in zip(missing, results):
            if isinstance(result, BaseException):
                failures += 1
                log.warning("Skipping %s: %s", coin_id, result)
            else:
                found[coin_id] = result
        return found, failures

    def _details_task(self, coin_id: str) -> "asyncio.Task[CoinDetails]":
        """Single flight per coin: if a lookup for this coin is already running
        (e.g. the startup warm-up), join it instead of calling CoinGecko again."""
        task = self._inflight.get(coin_id)
        if task is None:
            task = asyncio.create_task(self._fetch_and_cache(coin_id))
            self._inflight[coin_id] = task
            task.add_done_callback(lambda _: self._inflight.pop(coin_id, None))
        return task

    async def _fetch_and_cache(self, coin_id: str) -> CoinDetails:
        details = CoinDetails.from_api(await self._client.get_coin(coin_id))
        self._details.set(coin_id, details)
        return details