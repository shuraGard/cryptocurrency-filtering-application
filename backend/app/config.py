"""Application settings, loaded from environment variables or a local .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    # CoinGecko access
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str | None = None
    coingecko_rate_limit_per_min: int | None = None

    # Scan scope and performance knobs
    market_pages: int = 2  # pages of 250 coins, ordered by market cap
    max_detail_fetches: int = 60  # per-coin detail calls allowed per refresh
    markets_cache_ttl_seconds: int = 300
    details_cache_ttl_seconds: int = 1800

    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def effective_rate_limit(self) -> int:
        """Requests per minute to allow. CoinGecko's Demo plan permits ~30/min;
        keyless access is throttled much harder, so we stay conservative there."""
        if self.coingecko_rate_limit_per_min:
            return self.coingecko_rate_limit_per_min
        return 25 if self.coingecko_api_key else 8
