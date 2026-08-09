from __future__ import annotations

from backend.domain.ports.embedding_provider import EmbeddingProvider


class NoOpEmbeddingProvider(EmbeddingProvider):
    """Placeholder used until a real embedding API is wired in.

    RankingService only calls embed() when settings.embedding_enabled is True,
    so this should never actually run while embeddings are disabled (the default).
    Swap for a real implementation in infrastructure/embedding/ once an embedding
    API is chosen, without touching application/ or domain/.
    """

    async def embed(self, text: str, input_type: str = "query") -> list[float]:
        raise NotImplementedError(
            "Embedding API not configured yet — set EMBEDDING_ENABLED=true and "
            "provide EMBEDDING_API_URL/EMBEDDING_API_KEY, then swap in a real provider."
        )
