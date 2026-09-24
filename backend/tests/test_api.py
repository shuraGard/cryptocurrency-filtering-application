from fastapi.testclient import TestClient

from app.main import create_app, get_service
from app.service import ProjectService

from .conftest import FakeCoinGeckoClient, detail_payload, market_coin


def _client(settings, preview_listing: bool) -> TestClient:
    fake = FakeCoinGeckoClient(
        [market_coin().model_dump()],
        {"good-coin": detail_payload("good-coin", preview_listing=preview_listing)},
    )
    app = create_app(settings)
    app.dependency_overrides[get_service] = lambda: ProjectService(fake, settings)
    return TestClient(app)


def test_projects_endpoint_returns_filtered_rows(settings):
    response = _client(settings, preview_listing=True).get("/api/projects")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    row = body["items"][0]
    assert row["name"] == "Good Coin"
    assert row["tvl_usd"] == 200_000
    assert body["meta"]["scanned_coins"] == 1


def test_preview_listing_query_param(settings):
    client = _client(settings, preview_listing=False)

    assert client.get("/api/projects").json()["count"] == 0  # default 'true' excludes it
    assert client.get("/api/projects", params={"preview_listing": "any"}).json()["count"] == 1
    assert client.get("/api/projects", params={"preview_listing": "nope"}).status_code == 422


def test_health(settings):
    assert _client(settings, True).get("/api/health").json() == {"status": "ok"}
