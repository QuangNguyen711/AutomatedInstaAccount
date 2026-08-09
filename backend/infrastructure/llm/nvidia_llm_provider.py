from __future__ import annotations

import httpx

from backend.domain.ports.llm_provider import LLMProvider


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
        response = await self._client.post(
            self._chat_url,
            json={
                "model": self._model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self._max_tokens,
                # Low temperature: this is grounded summarization, not creative writing — at
                # the default temperature the model was observed live going off the rails into
                # random other-language tokens (Korean/Russian/Portuguese fragments) mid-summary.
                "temperature": self._temperature,
                "chat_template_kwargs": {"thinking": self._reasoning_enabled},
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
