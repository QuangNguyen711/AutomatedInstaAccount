from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str, input_type: str = "query") -> list[float]:
        """Return an embedding vector for the given text.

        input_type distinguishes a user query from a document/review being indexed —
        asymmetric retrieval models (like NV-EmbedQA) embed the two differently.
        """
