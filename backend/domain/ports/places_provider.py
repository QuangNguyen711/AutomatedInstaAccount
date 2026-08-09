from __future__ import annotations

from abc import ABC, abstractmethod

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
