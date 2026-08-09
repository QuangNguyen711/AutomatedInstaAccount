from __future__ import annotations

from abc import ABC, abstractmethod


class GeocodingProvider(ABC):
    @abstractmethod
    async def geocode(self, address: str) -> tuple[float, float] | None:
        """Resolve a free-text address to (lat, lng), or None if it can't be found."""
