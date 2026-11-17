from __future__ import annotations

import asyncio

import httpx

from backend.domain.ports.llm_provider import LLMProvider

# The NVIDIA endpoint intermittently returns 503/429/timeout under concurrent load. Without a
# retry, each such blip dropped that place's summary → RankingService couldn't set it → the
# completeness filter silently discarded the place, so only ~half the crawled places ever showed.
# Retrying transient failures recovers those instead of losing the whole result.
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_S = 1.5
_RETRIABLE_STATUS = {429, 500, 502, 503, 504}


class NvidiaLLMProvider(LLMProvider):
    """Calls NVIDIA's hosted Nemotron endpoint (OpenAI-compatible /chat/completions).

    Nemotron emits verbose chain-of-thought (`reasoning_content`) by default, which eats
    into max_tokens before any real answer appears — chat_template_kwargs.thinking=False
    (verified via manual curl testing) turns that off for short, direct outputs.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model_name: str,
        reasoning_enabled: bool = False,
        max_tokens: int = 250,
        temperature: float = 0.3,
        timeout_s: float = 45.0,
    ):
        self._chat_url = f"{api_url.rstrip('/')}/chat/completions"
        self._model_name = model_name
        self._reasoning_enabled = reasoning_enabled
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout_s
        )

    async def generate(self, prompt: str) -> str:
        payload = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self._max_tokens,
            # Low temperature: this is grounded summarization, not creative writing — at the
            # default temperature the model was observed live going off the rails into random
            # other-language tokens (Korean/Russian/Portuguese fragments) mid-summary.
            "temperature": self._temperature,
            # The vLLM Qwen proxy toggles reasoning via a top-level "thinking" flag (the earlier
            # NVIDIA Nemotron used chat_template_kwargs.thinking). Off by default: we want a short
            # grounded summary, not chain-of-thought eating into max_tokens.
            "thinking": self._reasoning_enabled,
        }

        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = await self._client.post(self._chat_url, json=payload)
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in _RETRIABLE_STATUS:
                    raise
                last_exc = exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc

            if attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(_RETRY_BACKOFF_S * (attempt + 1))

        assert last_exc is not None
        raise last_exc
