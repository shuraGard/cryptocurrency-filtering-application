"""Pydantic models: what we read from CoinGecko and what we return to clients."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MarketCoin(BaseModel):
    """The subset of a ``/coins/markets`` row that the filters and the UI need."""

    id: str
    symbol: str
    name: str
    image: str | None = None
    market_cap_rank: int | None = None
    current_price: float | None = None
    market_cap: float | None = None
    fully_diluted_valuation: float | None = None
    total_volume: float | None = None
    total_supply: float | None = None
    max_supply: float | None = None


class CoinDetails(BaseModel):
    """Fields that are only available from the per-coin ``/coins/{id}`` endpoint."""

    id: str
    preview_listing: bool = False
    tvl_usd: float | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "CoinDetails":
        market_data = payload.get("market_data") or {}
        return cls(
            id=payload["id"],
            preview_listing=bool(payload.get("preview_listing", False)),
            tvl_usd=parse_tvl(market_data.get("total_value_locked")),
        )


def parse_tvl(raw: Any) -> float | None:
    """CoinGecko documents ``total_value_locked`` as a number, but it is also
    seen as ``{"btc": ..., "usd": ...}`` or ``null``. Accept all three."""
    if isinstance(raw, dict):
        raw = raw.get("usd")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class Project(MarketCoin):
    """A coin with market data and per-coin details merged; the API's row type."""

    preview_listing: bool
    tvl_usd: float | None

    @classmethod
    def merge(cls, market: MarketCoin, details: CoinDetails) -> "Project":
        return cls(
            **market.model_dump(),
            preview_listing=details.preview_listing,
            tvl_usd=details.tvl_usd,
        )


class ScanMeta(BaseModel):
    """How the result was produced, so the client can explain it to the user."""

    fetched_at: datetime  # when the market snapshot was pulled from CoinGecko
    scanned_coins: int  # rows read from /coins/markets
    candidates: int  # rows that passed the cheap filters and got a detail lookup
    candidates_truncated: bool  # True if MAX_DETAIL_FETCHES cut the candidate list
    detail_failures: int  # candidates skipped because /coins/{id} failed


class ProjectsResponse(BaseModel):
    count: int
    items: list[Project]
    meta: ScanMeta
