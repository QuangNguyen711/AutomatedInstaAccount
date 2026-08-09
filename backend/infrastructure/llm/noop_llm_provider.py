from __future__ import annotations

from backend.domain.ports.llm_provider import LLMProvider


class NoOpLLMProvider(LLMProvider):
    """Placeholder used while settings.llm_enabled is False.

    SearchService only calls SummaryService (and therefore this) when llm_enabled is True,
    so this should never actually run with the default config.
    """

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError(
            "LLM API not enabled — set LLM_ENABLED=true and provide LLM_API_URL/LLM_API_KEY."
        )
