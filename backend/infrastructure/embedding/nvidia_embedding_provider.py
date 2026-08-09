from __future__ import annotations

import httpx

from backend.domain.ports.embedding_provider import EmbeddingProvider


class NvidiaEmbeddingProvider(EmbeddingProvider):
    """Calls NVIDIA's hosted nv-embedqa-e5-v5 endpoint (OpenAI-compatible /embeddings).

    input_type is a required, non-standard field for this model: it embeds a user "query"
    differently from a "passage" being indexed (asymmetric retrieval) — using the wrong one
    silently degrades similarity quality rather than erroring.
    """

    def __init__(self, api_url: str, api_key: str, model_name: str, timeout_s: float = 20.0):
        self._api_url = api_url
        self._model_name = model_name
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout_s
        )

    async def embed(self, text: str, input_type: str = "query") -> list[float]:
        response = await self._client.post(
            self._api_url,
            json={"input": [text], "model": self._model_name, "input_type": input_type},
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
