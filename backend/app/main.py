"""FastAPI application: wiring, lifecycle and the REST endpoints."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from .coingecko import CoinGeckoClient, CoinGeckoError
from .config import Settings
from .filters import FilterCriteria
from .schemas import ProjectsResponse
from .service import ProjectService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per CoinGecko call is too chatty

PreviewMode = Literal["true", "false", "any"]
_PREVIEW_MODES: dict[PreviewMode, bool | None] = {"true": True, "false": False, "any": None}


def get_service(request: Request) -> ProjectService:
    return request.app.state.service


router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/projects", response_model=ProjectsResponse)
async def list_projects(
    preview_listing: PreviewMode = Query(
        "true",
        description=(
            "Filter on CoinGecko's preview_listing flag. 'true' is the task's specification; "
            "'any' skips this check (useful because preview listings rarely have full market data)."
        ),
    ),
    service: ProjectService = Depends(get_service),
) -> ProjectsResponse:
    criteria = FilterCriteria(preview_listing=_PREVIEW_MODES[preview_listing])
    try:
        return await service.get_projects(criteria)
    except CoinGeckoError as exc:
        raise HTTPException(status_code=503, detail=f"CoinGecko is unavailable: {exc}") from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    client = CoinGeckoClient(
        base_url=settings.coingecko_base_url,
        api_key=settings.coingecko_api_key,
        rate_limit_per_min=settings.effective_rate_limit,
    )
    service = ProjectService(client, settings)
    app.state.service = service
    warm_up = asyncio.create_task(service.warm_up())
    try:
        yield
    finally:
        warm_up.cancel()
        await client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Crypto Project Screener", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
