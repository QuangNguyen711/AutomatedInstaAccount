from __future__ import annotations

from abc import ABC, abstractmethod


class ImageClassifierProvider(ABC):
    @abstractmethod
    async def is_good(self, image_url: str) -> bool:
        """Return True if the photo at image_url is worth showing to users."""
