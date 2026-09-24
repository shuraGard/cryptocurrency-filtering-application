from typing import Any

import pytest

from app.config import Settings
from app.schemas import MarketCoin


def market_coin(**overrides: Any) -> MarketCoin:
    """A coin that passes every market-level filter unless overridden."""
    base = dict(
        id="good-coin",
        symbol="good",
        name="Good Coin",
        market_cap=10_000_000,
        fully_diluted_valuation=20_000_000,
        total_volume=500_000,
        total_supply=1_000_000,
        max_supply=1_000_000,
    )
    return MarketCoin(**{**base, **overrides})


def detail_payload(coin_id: str, preview_listing: bool = True, tvl: Any = 200_000) -> dict[str, Any]:
    """Shape of a /coins/{id} response, reduced to the fields we read."""
    return {
        "id": coin_id,
        "preview_listing": preview_listing,
        "market_data": {"total_value_locked": tvl},
    }


class FakeCoinGeckoClient:
    """Stands in for CoinGeckoClient; serves canned pages and counts calls."""

    def __init__(self, markets: list[dict[str, Any]], details: dict[str, dict[str, Any]]):
        self.markets = markets
        self.details = details
        self.market_calls = 0
        self.detail_calls: list[str] = []

    async def get_markets(self, page: int, per_page: int = 250) -> list[dict[str, Any]]:
        self.market_calls += 1
        start = (page - 1) * per_page
        return self.markets[start : start + per_page]

    async def get_coin(self, coin_id: str) -> dict[str, Any]:
        self.detail_calls.append(coin_id)
        try:
            return self.details[coin_id]
        except KeyError:
            raise RuntimeError(f"no details for {coin_id}")

    async def aclose(self) -> None:
        pass


@pytest.fixture
def settings() -> Settings:
    return Settings(market_pages=1, max_detail_fetches=10, _env_file=None)
