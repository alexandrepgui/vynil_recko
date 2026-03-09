from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from logger import get_logger
from .base import LLMProvider, LLMResponse

log = get_logger("services.llm.openrouter")


class OpenRouterProvider:
    """LLM provider using the OpenRouter API (OpenAI-compatible)."""

    provider_name: str = "openrouter"

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

    def chat(self, messages: list[dict], model: str) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        log.debug("OpenRouter request: model=%s messages=%d", model, len(messages))
        resp = self._session.post(
            self._base_url,
            headers=headers,
            json={"model": model, "messages": messages},
        )
        log.debug("OpenRouter response: status=%d", resp.status_code)
        resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        log.debug("OpenRouter response length: %d chars", len(content))
        return LLMResponse(
            content=content,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            model=model,
            provider=self.provider_name,
        )
