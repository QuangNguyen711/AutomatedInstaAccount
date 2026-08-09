from __future__ import annotations

import asyncio

from backend.application.services.summary_service import SummaryService
from backend.config import Settings
from backend.domain.entities.place import Place
from backend.domain.entities.ranked_place import RankedPlace
from backend.domain.entities.search_query import SearchQuery
from backend.domain.geo import haversine_distance_m

# Caps concurrent LLM calls — one per place, run at every search (not just cache-miss) since
# the match score/summary depend on the query text and can't be precomputed at ingest time.
# Kept modest: the NVIDIA endpoint returned 503s under higher concurrency in testing.
_MAX_CONCURRENT_LLM_CALLS = 3


class RankingService:
    def __init__(self, summary_service: SummaryService, settings: Settings):
        self._summary_service = summary_service
        self._settings = settings
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_LLM_CALLS)

    async def rank(self, places: list[Place], query: SearchQuery) -> list[RankedPlace]:
        if not places:
            return []

        distances = {
            place.place_id: haversine_distance_m(query.lat, query.lng, place.lat, place.lng)
            for place in places
        }
        max_distance = max(distances.values()) or 1.0

        match_scores = await asyncio.gather(*(self._match(p, query) for p in places))

        ranked = []
        for place, llm_score in zip(places, match_scores):
            distance_m = distances[place.place_id]
            distance_score = 1 - (distance_m / max_distance)
            relevance_score = llm_score / 10.0

            score = (
                self._settings.ranking_weight_relevance * relevance_score
                + self._settings.ranking_weight_distance * distance_score
            )
            ranked.append(RankedPlace(place=place, score=score, distance_m=distance_m))

        ranked.sort(key=lambda rp: rp.score, reverse=True)
        return ranked

    async def _match(self, place: Place, query: SearchQuery) -> float:
        if not self._settings.llm_enabled:
            return 0.0
        try:
            async with self._semaphore:
                summary, score = await self._summary_service.generate_query_match(
                    place, query.query_text
                )
        except Exception:
            # One place's LLM call failing (rate limit, timeout, transient 503) shouldn't
            # 500 the whole search — that place just falls back to distance-only ranking.
            return 0.0
        place.summary = summary
        return score
