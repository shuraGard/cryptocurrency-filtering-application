"""The screening rules, as pure functions. No I/O here, so they are cheap to unit-test.

The task's criteria are split by *where the data comes from*:

* ``passes_market_filters`` uses fields present in ``/coins/markets`` (one call per
  250 coins) and runs first, so we only pay for per-coin detail calls on real
  candidates.
* ``passes_detail_filters`` uses ``preview_listing`` and TVL, which CoinGecko only
  exposes on ``/coins/{id}`` (one call per coin).
"""

import math
from dataclasses import dataclass

from .schemas import MarketCoin, Project


@dataclass(frozen=True)
class FilterCriteria:
    max_fdv_usd: float = 100_000_000
    min_volume_24h_usd: float = 50_000
    min_tvl_usd: float = 50_000
    # True / False to require that value; None to ignore the flag entirely.
    preview_listing: bool | None = True


def supplies_match(max_supply: float | None, total_supply: float | None) -> bool:
    """"Max supply equals total supply", tolerating float noise in CoinGecko's numbers."""
    if max_supply is None or total_supply is None:
        return False
    return math.isclose(max_supply, total_supply, rel_tol=1e-9)


def passes_market_filters(coin: MarketCoin, criteria: FilterCriteria) -> bool:
    return (
        (coin.market_cap or 0) > 0
        and coin.fully_diluted_valuation is not None
        and coin.fully_diluted_valuation < criteria.max_fdv_usd
        and (coin.total_volume or 0) > criteria.min_volume_24h_usd
        and supplies_match(coin.max_supply, coin.total_supply)
    )


def passes_detail_filters(project: Project, criteria: FilterCriteria) -> bool:
    if criteria.preview_listing is not None and project.preview_listing != criteria.preview_listing:
        return False
    return project.tvl_usd is not None and project.tvl_usd > criteria.min_tvl_usd
