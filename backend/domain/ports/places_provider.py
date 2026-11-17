from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from backend.domain.entities.place import Place
from backend.domain.entities.search_query import SearchQuery


class PlacesProvider(ABC):
    @abstractmethod
    async def search_listings(self, query: SearchQuery) -> list[Place]:
        """Find places matching the query's location/keyword — basic info only (name, address,
        coords, rating, a listing thumbnail). No reviews/detail photos yet; see fetch_details."""

    @abstractmethod
    async def fetch_details(self, places: list[Place]) -> None:
        """Scrape full detail (refined address, photos, reviews) for each place, mutating it
        in place. Call only for places that actually need a fresh detail scrape — this is the
        expensive part of a crawl."""

    @abstractmethod
    def fetch_details_stream(self, places: list[Place]) -> AsyncIterator[Place]:
        """Like fetch_details, but yields each place as its own detail scrape completes so
        callers can stream results. Yields exactly one item per input place."""
