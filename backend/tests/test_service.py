import asyncio

from app.filters import FilterCriteria
from app.service import ProjectService

from .conftest import FakeCoinGeckoClient, detail_payload, market_coin


def _run(coro):
    return asyncio.run(coro)


def test_pipeline_filters_and_only_fetches_details_for_candidates(settings):
    markets = [
        market_coin(id="keep").model_dump(),
        market_coin(id="no-tvl").model_dump(),
        market_coin(id="not-preview").model_dump(),
        market_coin(id="too-big", fully_diluted_valuation=500_000_000).model_dump(),
    ]
    details = {
        "keep": detail_payload("keep"),
        "no-tvl": detail_payload("no-tvl", tvl=None),
        "not-preview": detail_payload("not-preview", preview_listing=False),
        "too-big": detail_payload("too-big"),
    }
    client = FakeCoinGeckoClient(markets, details)
    service = ProjectService(client, settings)

    response = _run(service.get_projects(FilterCriteria()))

    assert [item.id for item in response.items] == ["keep"]
    assert response.count == 1
    assert response.meta.scanned_coins == 4
    assert response.meta.candidates == 3
    assert sorted(client.detail_calls) == ["keep", "no-tvl", "not-preview"]  # "too-big" never looked up


def test_second_request_is_served_from_cache(settings):
    client = FakeCoinGeckoClient([market_coin().model_dump()], {"good-coin": detail_payload("good-coin")})
    service = ProjectService(client, settings)

    async def twice():
        await service.get_projects(FilterCriteria())
        # A different preview mode reuses both caches; only the pure filters re-run.
        return await service.get_projects(FilterCriteria(preview_listing=None))

    response = _run(twice())

    assert response.count == 1
    assert client.market_calls == 1
    assert client.detail_calls == ["good-coin"]


def test_detail_fetches_are_capped_and_flagged(settings):
    settings.max_detail_fetches = 2
    markets = [market_coin(id=f"c{i}", market_cap=1_000_000 * (i + 1)).model_dump() for i in range(5)]
    details = {f"c{i}": detail_payload(f"c{i}") for i in range(5)}
    client = FakeCoinGeckoClient(markets, details)
    service = ProjectService(client, settings)

    response = _run(service.get_projects(FilterCriteria()))

    assert response.meta.candidates_truncated is True
    assert response.meta.candidates == 2
    assert sorted(client.detail_calls) == ["c3", "c4"]  # the two largest by market cap


def test_failed_detail_lookup_skips_that_coin_only(settings):
    markets = [market_coin(id="ok").model_dump(), market_coin(id="broken").model_dump()]
    client = FakeCoinGeckoClient(markets, {"ok": detail_payload("ok")})
    service = ProjectService(client, settings)

    response = _run(service.get_projects(FilterCriteria()))

    assert [item.id for item in response.items] == ["ok"]
    assert response.meta.detail_failures == 1


def test_concurrent_requests_share_detail_lookups(settings):
    """A request arriving while the warm-up is still running must not repeat its calls."""
    markets = [market_coin(id=f"c{i}").model_dump() for i in range(3)]
    client = FakeCoinGeckoClient(markets, {f"c{i}": detail_payload(f"c{i}") for i in range(3)})
    service = ProjectService(client, settings)

    async def concurrently():
        return await asyncio.gather(service.get_projects(FilterCriteria()), service.get_projects(FilterCriteria()))

    first, second = _run(concurrently())

    assert first.count == second.count == 3
    assert client.market_calls == 1
    assert sorted(client.detail_calls) == ["c0", "c1", "c2"]  # each coin looked up exactly once