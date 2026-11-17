from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace

from backend.application.services.query_rewrite_service import QueryRewriteService
from backend.application.services.ranking_service import RankingService
from backend.config import Settings
from backend.domain.entities.place import Photo, Place
from backend.domain.entities.ranked_place import RankedPlace
from backend.domain.entities.search_query import SearchQuery
from backend.domain.geo import haversine_distance_m
from backend.domain.ports.image_classifier_provider import ImageClassifierProvider
from backend.domain.ports.place_repository import PlaceRepository
from backend.domain.ports.places_provider import PlacesProvider

# Caps concurrent photo-classify calls when ingesting a freshly-crawled batch of places.
_MAX_CONCURRENT_ENRICHMENT_CALLS = 10
# A card's photo grid has 4 slots (see place_card.html). A place must have at least this many
# photos (total) to fill the grid + an LLM summary to show — otherwise it reads as a broken card.
_MIN_PHOTOS_TO_DISPLAY = 4
# How many classifier-approved ("good") photos to try to surface for the grid. This is only an
# ORDERING target now (best photos first), NOT a display gate: the YOLO filter rejects most
# legitimate cafe shots, so gating on 4 good photos was silently dropping ~half of otherwise-fine
# places (they had reviews + summary, just few photos the classifier happened to like).
_MIN_GOOD_PHOTOS_TO_DISPLAY = 4
# Classify photos in batches and stop once enough are good: a card only ever shows
# _MIN_GOOD_PHOTOS_TO_DISPLAY, so downloading + running YOLO on all ~20 scraped photos per place
# is wasted work. Batch a bit above the target so a single batch usually already clears the bar.
_PHOTO_CLASSIFY_BATCH_SIZE = 6
# Must match PlaywrightPlacesProvider._build_search_url's own fallback — what an empty/blank
# query normalizes to before being sent to Maps.
_DEFAULT_SEARCH_TERM = "quan an quan cafe"


class SearchService:
    def __init__(
        self,
        places_provider: PlacesProvider,
        place_repository: PlaceRepository,
        image_classifier: ImageClassifierProvider,
        ranking_service: RankingService,
        query_rewrite_service: QueryRewriteService,
        settings: Settings,
    ):
        self._places_provider = places_provider
        self._place_repository = place_repository
        self._image_classifier = image_classifier
        self._ranking_service = ranking_service
        self._query_rewrite_service = query_rewrite_service
        self._settings = settings
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_ENRICHMENT_CALLS)

    async def search(self, query: SearchQuery) -> list[RankedPlace]:
        # Google Maps' search box can't match detailed requirements ("must have dark chocolate
        # cake") — only place categories/names. The full original query is kept for review-based
        # ranking below, which is where those specific requirements actually get evaluated.
        search_term = _DEFAULT_SEARCH_TERM
        if query.query_text.strip():
            search_term = (
                await self._query_rewrite_service.simplify_for_maps(query.query_text)
                if self._settings.llm_enabled
                else query.query_text.strip()
            )

        # The listing search always runs fresh — it's what makes the results actually match the
        # current query (a "cafe" search must never reuse places from an earlier, unrelated
        # "bánh" search). Caching only kicks in per place below, for the expensive detail scrape
        # (photos/reviews): if we've already crawled *this specific place* recently, reuse that
        # instead of re-scraping it, regardless of which search found it this time.
        crawl_query = replace(query, query_text=search_term)
        listings = await self._places_provider.search_listings(crawl_query)
        listings = listings[: self._settings.max_detail_pages]

        places: list[Place] = []
        need_details: list[Place] = []
        for listing in listings:
            cached = await self._place_repository.find_by_id(
                listing.place_id, self._settings.cache_ttl_days
            )
            if cached is not None:
                places.append(cached)
            else:
                need_details.append(listing)

        if need_details:
            await self._places_provider.fetch_details(need_details)
            await asyncio.gather(*(self._classify_photos(place) for place in need_details))
            await self._place_repository.upsert(need_details)
            places.extend(need_details)

        # Ranking (and the per-place summary shown alongside it) depends on the query text, so
        # it always runs here — even for reused cached places, which carry no query context.
        ranked = await self._ranking_service.rank(places, query)

        complete: list[RankedPlace] = []
        incomplete_ids: list[str] = []
        for rp in ranked:
            if self._is_display_ready(rp):
                complete.append(rp)
            else:
                incomplete_ids.append(rp.place.place_id)

        if incomplete_ids:
            # Missing photos/summary usually means the scrape itself was incomplete (blur
            # filter ate everything, reviews tab flaked) rather than the place genuinely
            # lacking content — drop the stale cache entry so it gets re-crawled from scratch.
            await self._place_repository.delete(incomplete_ids)

        return complete

    async def _simplify_query(self, query: SearchQuery) -> str:
        if not query.query_text.strip():
            return _DEFAULT_SEARCH_TERM
        if self._settings.llm_enabled:
            return await self._query_rewrite_service.simplify_for_maps(query.query_text)
        return query.query_text.strip()

    async def search_stream(self, query: SearchQuery) -> AsyncIterator[RankedPlace]:
        """Streaming variant of search(): yields each display-ready place as soon as it's
        finished (cached ones almost immediately; freshly-crawled ones as each detail scrape +
        photo classification + LLM scoring completes), so the UI can render results progressively
        instead of waiting for the whole batch. Emission is in completion order — the client
        re-sorts by score as cards arrive."""
        search_term = await self._simplify_query(query)
        crawl_query = replace(query, query_text=search_term)

        listings = await self._places_provider.search_listings(crawl_query)
        listings = listings[: self._settings.max_detail_pages]
        if not listings:
            return

        # Distances come from the listing coords (embedded in each result's href), so the
        # distance half of the score is known before any detail scrape — no need to wait.
        distances = {
            p.place_id: haversine_distance_m(query.lat, query.lng, p.lat, p.lng)
            for p in listings
        }
        max_distance = max(distances.values()) or 1.0

        cached: list[Place] = []
        need_details: list[Place] = []
        for listing in listings:
            hit = await self._place_repository.find_by_id(
                listing.place_id, self._settings.cache_ttl_days
            )
            (cached if hit is not None else need_details).append(hit or listing)

        out_queue: asyncio.Queue = asyncio.Queue()
        done_marker = object()
        retry_candidates: list[Place] = []

        async def _finish(place: Place, needs_ingest: bool, is_retry: bool = False) -> None:
            try:
                if needs_ingest:
                    await self._classify_photos(place)
                    await self._place_repository.upsert([place])
                ranked = await self._ranking_service.score_place(
                    place, query, distances.get(place.place_id, max_distance), max_distance
                )
                if self._is_display_ready(ranked):
                    await out_queue.put(ranked)
                elif needs_ingest and not is_retry:
                    # Fresh crawl came back incomplete (reviews tab flaked under concurrent load /
                    # too few good photos). Queue it for one more from-scratch scrape in THIS same
                    # request — a fresh page navigation usually succeeds where the first didn't.
                    # This automates what the user was doing by hand (re-running the search until
                    # the missing places filled in).
                    retry_candidates.append(place)
                elif needs_ingest:
                    # Still incomplete after the retry — drop so it's re-tried on a later search.
                    await self._place_repository.delete([place.place_id])
            except Exception:
                pass
            finally:
                await out_queue.put(done_marker)

        for place in cached:
            asyncio.create_task(_finish(place, needs_ingest=False))

        async def _drive(places: list[Place], is_retry: bool) -> None:
            async for place in self._places_provider.fetch_details_stream(places):
                asyncio.create_task(_finish(place, needs_ingest=True, is_retry=is_retry))

        # First pass: cached places (already scheduled above) + a fresh crawl of the rest.
        drive_task = asyncio.create_task(_drive(need_details, is_retry=False))
        remaining = len(cached) + len(need_details)
        while remaining > 0:
            item = await out_queue.get()
            if item is done_marker:
                remaining -= 1
                continue
            yield item
        await drive_task

        # Retry pass: re-crawl (from scratch) the fresh places that came back incomplete.
        if retry_candidates:
            batch = retry_candidates[:]
            retry_candidates.clear()
            for place in batch:
                # The scraper appends reviews without de-duping, so clear the partial set before
                # re-scraping. Photos are de-duped by URL, so leave them (the retry only adds).
                place.reviews.clear()
            retry_task = asyncio.create_task(_drive(batch, is_retry=True))
            remaining = len(batch)
            while remaining > 0:
                item = await out_queue.get()
                if item is done_marker:
                    remaining -= 1
                    continue
                yield item
            await retry_task

    @staticmethod
    def _is_display_ready(ranked_place: RankedPlace) -> bool:
        good_photos = [p for p in ranked_place.place.photos if p.is_good]
        return (
            len(good_photos) >= _MIN_GOOD_PHOTOS_TO_DISPLAY
            and bool(ranked_place.place.summary)
        )

    async def _classify_photos(self, place: Place) -> None:
        # Classify in batches, stopping once enough photos are good — most photos then never get
        # downloaded/classified at all. Photos left unclassified keep is_good=None (treated as
        # not-good downstream), which is fine: the card only needs _MIN_GOOD_PHOTOS_TO_DISPLAY.
        good = 0
        for start in range(0, len(place.photos), _PHOTO_CLASSIFY_BATCH_SIZE):
            batch = place.photos[start : start + _PHOTO_CLASSIFY_BATCH_SIZE]
            results = await asyncio.gather(*(self._classify_photo(photo) for photo in batch))
            good += sum(results)
            if good >= _MIN_GOOD_PHOTOS_TO_DISPLAY:
                break

    async def _classify_photo(self, photo: Photo) -> bool:
        async with self._semaphore:
            photo.is_good = await self._image_classifier.is_good(photo.url)
        return bool(photo.is_good)
