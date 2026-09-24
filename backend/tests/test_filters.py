import pytest

from app.filters import FilterCriteria, passes_detail_filters, passes_market_filters, supplies_match
from app.schemas import CoinDetails, Project, parse_tvl

from .conftest import market_coin

CRITERIA = FilterCriteria()


def test_baseline_coin_passes_market_filters():
    assert passes_market_filters(market_coin(), CRITERIA)


@pytest.mark.parametrize(
    "overrides",
    [
        {"market_cap": 0},
        {"market_cap": None},
        {"fully_diluted_valuation": 100_000_000},  # must be strictly below
        {"fully_diluted_valuation": None},
        {"total_volume": 50_000},  # must be strictly above
        {"total_volume": None},
        {"max_supply": None},
        {"max_supply": 2_000_000},
    ],
)
def test_market_filter_rejections(overrides):
    assert not passes_market_filters(market_coin(**overrides), CRITERIA)


def test_supply_match_tolerates_float_noise():
    assert supplies_match(1_000_000.0, 1_000_000.0000001)
    assert not supplies_match(1_000_000, 1_000_001)
    assert not supplies_match(None, 1)


def _project(preview_listing: bool, tvl: float | None) -> Project:
    return Project.merge(market_coin(), CoinDetails(id="good-coin", preview_listing=preview_listing, tvl_usd=tvl))


def test_detail_filters_require_preview_and_tvl():
    assert passes_detail_filters(_project(True, 60_000), CRITERIA)
    assert not passes_detail_filters(_project(False, 60_000), CRITERIA)
    assert not passes_detail_filters(_project(True, 50_000), CRITERIA)
    assert not passes_detail_filters(_project(True, None), CRITERIA)


def test_preview_listing_can_be_ignored_or_inverted():
    assert passes_detail_filters(_project(False, 60_000), FilterCriteria(preview_listing=None))
    assert passes_detail_filters(_project(False, 60_000), FilterCriteria(preview_listing=False))
    assert not passes_detail_filters(_project(True, 60_000), FilterCriteria(preview_listing=False))


@pytest.mark.parametrize(
    "raw, expected",
    [
        (123.5, 123.5),
        ({"btc": 1.2, "usd": 456.0}, 456.0),
        ({"btc": 1.2}, None),
        (None, None),
        ("not-a-number", None),
    ],
)
def test_parse_tvl_accepts_documented_and_observed_shapes(raw, expected):
    assert parse_tvl(raw) == expected
