# PlacesFinder

A personal search engine for finding cafes/restaurants near you that match a specific
free-text request (a dish, an atmosphere, an amenity...). Google Maps is scraped on-demand
with Playwright/Patchright (no paid Places API), cached per-place in Postgres, and each
result is scored + given a short summary by an LLM reading its real reviews — weighted
toward recent ones — against your exact request.

This project supersedes the original TikTok/Instagram coffee-shop-review pipeline, which
is archived under [`legacy/`](legacy/) (old Selenium crawlers, the YOLO training data, and
the `best_cls.pt` photo-quality classifier — the classifier is reused live, see
`backend/infrastructure/vision/`).

## How a search works

1. **Query rewrite** (`QueryRewriteService`) — your free-text request gets simplified into a
   short term Google Maps' own search box can actually match on (place category/name only;
   Maps can't search on "must have dark chocolate cake"). This simplified term is what's
   actually sent to Maps.
2. **Listing search** (`PlacesProvider.search_listings`) — always runs fresh, so results
   genuinely reflect the current query.
3. **Per-place detail cache** (`PlaceRepository.find_by_id`) — for each listing, a place's own
   photos/reviews are reused if already crawled within `CACHE_TTL_DAYS`, regardless of which
   search found it; otherwise `PlacesProvider.fetch_details` scrapes it fresh (photos including
   ones attached to reviews, filtered for blur, plus reviews with rating/recency).
4. **Ranking** (`RankingService` + `SummaryService`) — your *full, original* request (not the
   simplified Maps term) is matched against each place's real reviews by an LLM, producing a
   0-10 relevance score and a one-sentence grounded summary. Final rank = weighted relevance +
   distance (`RANKING_WEIGHT_RELEVANCE` / `RANKING_WEIGHT_DISTANCE`).
5. **Completeness filter** — a result needs both a summary and at least 4 good photos to be
   shown; anything short of that gets its stale cache entry dropped so it's re-crawled next time
   instead of surfacing a half-empty card.

## Architecture

Clean Architecture, mirroring the layer split used in the sibling SlideGen project:

```
backend/
├── api/              # FastAPI routes, Jinja2 templates, static assets (presentation layer)
├── application/      # Services orchestrating use cases (search, ranking, query rewrite)
├── domain/            # Entities + Ports (interfaces) — pure Python, no third-party deps
└── infrastructure/    # Concrete implementations: Playwright scraper, Postgres repo, YOLO
                        # classifier, NVIDIA-hosted LLM, Nominatim geocoding
```

Swapping the data source later (e.g. to the Google Places API once this goes public) means
adding one new `infrastructure/places/` implementation of the `PlacesProvider` port — nothing
in `application/`, `domain/`, or `api/` needs to change.

## Requirements

- [uv](https://docs.astral.sh/uv/) for Python env/deps
- Docker Desktop, for building/running the app + Postgres locally
- A Google account signed in once via `scripts/google_login_setup.py` (see below) — without
  it, Maps serves a stripped "limited view" with no reviews to logged-out/automated sessions
- An NVIDIA API key (free tier) for the LLM ranking/summary/query-rewrite calls — without one,
  results still work but fall back to distance-only ranking with no summaries

## One-time setup: Google login

```bash
uv sync
uv run python scripts/google_login_setup.py
```

Opens a real (headed) browser for an interactive login, then saves the session to
`.secrets/google_auth_state.json` (gitignored). The account's **language must be set to
English** in its Google Account settings — the scraper matches Maps UI elements by English
text, and Maps follows the account's language once signed in, not the browser locale.
Re-run this whenever the session gets invalidated (Google occasionally forces this).

## Running locally

```bash
cp .env.example .env        # fill in LLM_API_KEY at minimum
docker compose up --build   # builds the app image (Chromium for Patchright + Xvfb) and starts Postgres+pgvector
uv run alembic upgrade head # first run only
```

Then open http://localhost:8000 — allow location access (or enter an address/Plus
Code/coordinates manually — useful on mobile, since browsers block geolocation on
non-HTTPS origins) and search.

### Running the API without Docker (Postgres still via Docker)

```bash
docker compose up -d db     # Postgres only
uv sync                     # install deps + create .venv
uv run alembic upgrade head
uv run uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

Note: the scraper runs Chromium **headed** (Google Maps' review tab bar doesn't render in
headless mode) — on Windows/macOS this just opens a visible browser window; the Docker image
runs it under Xvfb instead.

## Current scope

- ✅ On-demand Google Maps scraping (listing + review/photo detail pages), per-place Postgres
  cache with TTL, YOLO + blur-filter photo quality filtering.
- ✅ LLM-based ranking: query-aware relevance score + grounded summary per place, distance
  blended in, incomplete results filtered out and re-crawled.
- ✅ Manual address/Plus Code/coordinate entry as a geolocation fallback.
- ⏳ Swapping the scraper for the official Google Places API once this is opened up beyond
  personal use.
