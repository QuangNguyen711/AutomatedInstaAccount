from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.entities.place import Place


class PlaceRepository(ABC):
    @abstractmethod
    async def find_by_id(self, place_id: str, ttl_days: int) -> Place | None:
        """Return the cached place (with photos/reviews) if present and fetched within
        ttl_days, else None. Caching is per-place, not per-search — a place's detail data is
        reusable regardless of what search query found it again."""

    @abstractmethod
    async def upsert(self, places: list[Place]) -> None:
        """Persist/update places, along with their reviews and photos, in the cache."""

    @abstractmethod
    async def delete(self, place_ids: list[str]) -> None:
        """Remove places (and their cascaded reviews/photos) from the cache."""
