# Crypto Project Screener

A small full-stack app that pulls cryptocurrency projects from the CoinGecko API,
keeps the ones that match a fixed set of screening rules, and lets you search,
filter and sort the result in the browser.

```
Browser (React + Vite)  ──►  FastAPI backend  ──►  CoinGecko API
   search / FDV cap /          filtering,            /coins/markets
   sorting (client side)       caching, rate         /coins/{id}
                               limiting
```

The frontend only ever talks to the backend (`/api/*`); the backend is the only
component that calls CoinGecko.

## Screening rules (backend)

| Rule | Source field | Where it is checked |
| --- | --- | --- |
| Market cap > 0 | `market_cap` | `/coins/markets` |
| FDV < $100M | `fully_diluted_valuation` | `/coins/markets` |
| 24h volume > $50k | `total_volume` | `/coins/markets` |
| Max supply = total supply | `max_supply`, `total_supply` | `/coins/markets` |
| `preview_listing == true` | `preview_listing` | `/coins/{id}` (per coin) |
| TVL > $50k | `market_data.total_value_locked` | `/coins/{id}` (per coin) |

The last two fields are **not** part of `/coins/markets`, so they cost one request
per coin. That drives most of the design decisions below.

## Running it

Requirements: Python 3.11+, Node 18+.

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then put your CoinGecko Demo key into COINGECKO_API_KEY
uvicorn app.main:app --reload
```

* API: <http://localhost:8000/api/projects> (interactive docs at <http://localhost:8000/docs>)
* A free Demo API key (<https://www.coingecko.com/en/developers/dashboard>) is optional
  but strongly recommended: without it CoinGecko throttles keyless traffic hard and
  the first load is several times slower.
* On startup the backend warms its cache in the background. The very first result
  takes roughly 2–3 minutes with a Demo key (2 market-page calls + up to 60 per-coin
  calls at 25 requests/min); after that responses are instant until the cache expires.

Tests (no network needed):

```bash
cd backend && pytest
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to
`http://localhost:8000`, so no CORS or URL configuration is needed. For a
production build (`npm run build`) set `VITE_API_BASE` to the backend URL.

## API

### `GET /api/projects`

Query parameters:

| Name | Values | Default | Meaning |
| --- | --- | --- | --- |
| `preview_listing` | `true`, `false`, `any` | `true` | `true` is the task's rule. `any` skips the check; see *Assumptions* for why this exists. |

Response:

```json
{
  "count": 1,
  "items": [
    {
      "id": "example-coin",
      "symbol": "exc",
      "name": "Example Coin",
      "image": "https://coin-images.coingecko.com/...",
      "market_cap_rank": 712,
      "current_price": 0.42,
      "market_cap": 21000000,
      "fully_diluted_valuation": 42000000,
      "total_volume": 310000,
      "total_supply": 100000000,
      "max_supply": 100000000,
      "preview_listing": true,
      "tvl_usd": 1800000
    }
  ],
  "meta": {
    "fetched_at": "2026-09-24T12:00:00Z",
    "scanned_coins": 500,
    "candidates": 37,
    "candidates_truncated": false,
    "detail_failures": 0
  }
}
```

`meta` tells the client how the list was produced (how many coins were scanned,
how many needed a per-coin lookup, whether the lookup cap was hit). Errors from
CoinGecko surface as `503` with a message.

### `GET /api/health`

Returns `{"status": "ok"}`.

## How it works

### Backend (`backend/app`)

| Module | Responsibility |
| --- | --- |
| `coingecko.py` | Async HTTP client for CoinGecko. Adds the API key header, spaces requests to stay under the per-minute quota, retries on 429/5xx honouring `Retry-After`. |
| `filters.py` | The screening rules as pure functions (`FilterCriteria`, `passes_market_filters`, `passes_detail_filters`). No I/O. |
| `service.py` | The pipeline: markets → cheap filters → per-coin details for candidates → detail filters. Owns the caches. |
| `cache.py` | Tiny in-memory TTL cache. |
| `schemas.py` | Pydantic models for what we read from CoinGecko and what we return. |
| `main.py` | FastAPI wiring: settings, lifespan (client + background warm-up), CORS, routes. |
| `config.py` | Settings from environment / `.env`. |

Performance choices, in order of impact:

1. **Cheap filters first.** Market cap, FDV, volume and supply are checked on the
   250-coins-per-call `/coins/markets` payload. Only coins that survive get the
   per-coin `/coins/{id}` call (needed for `preview_listing` and TVL). In practice
   this turns hundreds of coins into a few dozen lookups.
2. **Rate limiting instead of hoping.** A small limiter spaces all outgoing requests
   evenly (25/min with a key, 8/min without, configurable), so we never trip 429s
   in normal operation; if we do, the client backs off and retries.
3. **Two caches.** The market snapshot is cached for 5 minutes; per-coin details for
   30 minutes (TVL and the preview flag change slowly). A refresh therefore only
   pays for coins that are *new* candidates. Concurrent requests during a refresh
   share the work instead of each hitting CoinGecko: one lock around the market
   fetch, and in-flight per-coin lookups are joined rather than repeated (so opening
   the UI while the startup warm-up runs does not double the wait).
4. **Bounded work.** `MAX_DETAIL_FETCHES` caps per-coin calls per refresh (largest
   market caps first) and the response flags `candidates_truncated` so the UI can say
   so. `MARKET_PAGES` bounds how far down the market-cap ranking we scan.
5. **Warm-up on startup** so the first browser request usually hits a warm cache.

### Frontend (`frontend/src`)

| File | Responsibility |
| --- | --- |
| `api.js` | The single `fetch` call to the backend. |
| `hooks/useProjects.js` | Loading / error / data state, re-fetch on mode change, abort on unmount. |
| `utils/projects.js` | Pure function that applies search, the extra FDV cap and sorting. |
| `components/Controls.jsx` | Search box, max-FDV input, sort field + direction, preview-listing mode, refresh. |
| `components/ProjectTable.jsx` | The table, with the sorted column highlighted and an empty state. |
| `App.jsx` | Composes the above and renders status / error / empty states. |

Search, the additional FDV filter and sorting run **in the browser**. After the
backend's screening the list is small (tens of rows, not thousands), so client-side
refinement gives instant feedback and costs zero extra API calls. If the dataset
grew, these would become query parameters on `/api/projects` together with
pagination; the pure `applyViewOptions` function would move server-side more or
less unchanged.

## What is completed

- [x] Backend REST endpoint returning the filtered list, with rate limiting, caching, retries and a background warm-up
- [x] All six screening rules from the task
- [x] Frontend listing the backend's projects
- [x] Additional user-defined "FDV below X" filter
- [x] Partial-match search by name (also matches the ticker symbol, e.g. `eth` → Ethereum)
- [x] Sorting by market cap and by 24h volume, both directions
- [x] Loading, error and empty states; the UI explains when a cap or a lookup failure affected the result
- [x] 25 backend unit/integration tests (filters, pipeline, caching, request de-duplication, truncation, endpoint) that run without network
- [x] This README

## Assumptions and limitations

1. **`preview_listing == true` vs. `market cap > 0`.** CoinGecko's *preview listing*
   flag marks coins that were added to the site but do not yet have complete market
   data. Requiring it *and* a positive market cap, volume and TVL is a very narrow
   combination and may leave an empty list at any given moment. I implemented the
   rule exactly as specified (default), but exposed `preview_listing=true|false|any`
   on the endpoint and in the UI so the rest of the app stays usable and the effect
   of that single rule is easy to see. The UI's empty state points to this switch.
2. **TVL source.** TVL is only available on `/coins/{id}` and only for coins CoinGecko
   tracks TVL for (mostly DeFi protocols). Coins with no TVL value cannot satisfy
   "TVL > $50k" and are excluded. CoinGecko documents the field as a number but it
   is also returned as `{"btc": …, "usd": …}`; both shapes are handled (USD is used).
3. **Scan scope.** By default the backend scans the top 500 coins by market cap
   (`MARKET_PAGES=2`). This is a deliberate trade-off between coverage and
   CoinGecko's rate limit; raise `MARKET_PAGES` / `MAX_DETAIL_FETCHES` to scan deeper.
   The app does not claim to cover CoinGecko's entire coin universe.
4. **"Max supply equals total supply"** requires both values to be present and equal
   within a relative tolerance of 1e-9 (to absorb float representation noise). Coins
   with `max_supply: null` (uncapped supply) do not qualify.
5. **Inequalities are strict**, as written in the task (`>` and `<`, not `>=`/`<=`).
   All money values are in USD.
6. **Search** matches the project name *or* its symbol (case-insensitive substring),
   since users commonly type tickers.
7. **Failures are per coin.** If a single `/coins/{id}` call keeps failing, that coin
   is skipped and counted in `meta.detail_failures` instead of failing the whole
   request.
8. **Caching is in-memory and per process.** Fine for a single-instance service;
   several workers would each keep their own cache (see *Next steps*).
9. The frontend has no automated tests, and the UI was kept deliberately plain.

## What I would do next

- Move search, FDV cap, sorting and pagination to backend query parameters once the
  result set is large enough to justify it.
- Refresh the cache on a schedule in the background (stale-while-revalidate), so no
  user request ever waits for CoinGecko; back the cache with Redis for multi-process
  deployments.
- Frontend tests (Vitest + React Testing Library) for `applyViewOptions` and the
  table/empty states.
- `docker-compose.yml` to start both services with one command, and serve the built
  frontend from FastAPI for a single-origin deployment.
- Clickable column headers for sorting and a few more columns (price change, rank).

## Project structure

```
backend/
  app/
    main.py        FastAPI app and routes
    service.py     fetch → filter → cache pipeline
    coingecko.py   CoinGecko client (rate limit, retries)
    filters.py     screening rules
    schemas.py     Pydantic models
    cache.py       TTL cache
    config.py      settings
  tests/           pytest suite (fake CoinGecko client, no network)
  requirements.txt
  .env.example
frontend/
  src/
    App.jsx
    api.js
    hooks/useProjects.js
    utils/projects.js, utils/format.js
    components/Controls.jsx, components/ProjectTable.jsx
    styles.css
  vite.config.js   dev proxy /api → backend
  package.json
```