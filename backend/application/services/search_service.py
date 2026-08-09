from __future__ import annotations

import asyncio
from dataclasses import replace

from backend.application.services.query_rewrite_service import QueryRewriteService
from backend.application.services.ranking_service import RankingService
from backend.config import Settings
from backend.domain.entities.place import Photo, Place
from backend.domain.entities.ranked_place import RankedPlace
from backend.domain.entities.search_query import SearchQuery
from backend.domain.ports.image_classifier_provider import ImageClassifierProvider
from backend.domain.ports.place_repository import PlaceRepository
from backend.domain.ports.places_provider import PlacesProvider

# Caps concurrent photo-classify calls when ingesting a freshly-crawled batch of places.
_MAX_CONCURRENT_ENRICHMENT_CALLS = 10
# A card's photo grid has 4 slots (see place_card.html) — fewer good photos than that, or no
# LLM summary (no reviews / review-matching failed), reads as a broken card rather than a
# genuinely sparse one, so it's dropped from the response.
_MIN_GOOD_PHOTOS_TO_DISPLAY = 4
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

    @staticmethod
    def _is_display_ready(ranked_place: RankedPlace) -> bool:
        good_photos = [p for p in ranked_place.place.photos if p.is_good]
        return (
            len(good_photos) >= _MIN_GOOD_PHOTOS_TO_DISPLAY
            and bool(ranked_place.place.summary)
        )

    async def _classify_photos(self, place: Place) -> None:
        await asyncio.gather(*(self._classify_photo(photo) for photo in place.photos))

    async def _classify_photo(self, photo: Photo) -> None:
        async with self._semaphore:
            photo.is_good = await self._image_classifier.is_good(photo.url)
