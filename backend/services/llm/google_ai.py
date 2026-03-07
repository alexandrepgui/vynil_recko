from __future__ import annotations

import base64

from google import genai
from google.genai import types

from logger import get_logger
from .base import LLMProvider, LLMResponse

log = get_logger("services.llm.google_ai")


def _translate_messages(messages: list[dict]) -> tuple[list[types.Content], str | None]:
    """Convert OpenAI-format messages to Gemini Content objects.

    Returns (contents, system_instruction).
    """
    system_instruction = None
    contents: list[types.Content] = []

    for msg in messages:
        role = msg["role"]
        if role == "system":
            system_instruction = msg["content"] if isinstance(msg["content"], str) else None
            continue

        # Map roles: user -> user, assistant -> model
        gemini_role = "model" if role == "assistant" else "user"
        raw_content = msg["content"]

        if isinstance(raw_content, str):
            contents.append(types.Content(role=gemini_role, parts=[types.Part.from_text(text=raw_content)]))
            continue

        # Multi-part content (list of dicts with type: text/image_url)
        parts: list[types.Part] = []
        for part in raw_content:
            if part["type"] == "text":
                parts.append(types.Part.from_text(text=part["text"]))
            elif part["type"] == "image_url":
                url = part["image_url"]["url"]
                # Parse data URI: "data:image/jpeg;base64,..."
                if url.startswith("data:"):
                    header, b64_data = url.split(",", 1)
                    mime_type = header.split(":")[1].split(";")[0]
                    image_bytes = base64.b64decode(b64_data)
                    parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
                else:
                    parts.append(types.Part.from_uri(file_uri=url, mime_type="image/jpeg"))

        contents.append(types.Content(role=gemini_role, parts=parts))

    return contents, system_instruction


class GoogleAIProvider:
    """LLM provider using the Google AI (Gemini) API directly."""

    provider_name: str = "google"

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def chat(self, messages: list[dict], model: str) -> LLMResponse:
        # Strip "google/" prefix if present (OpenRouter format)
        gemini_model = model.removeprefix("google/")

        contents, system_instruction = _translate_messages(messages)

        config = types.GenerateContentConfig()
        if system_instruction:
            config.system_instruction = system_instruction

        log.debug("Google AI request: model=%s messages=%d", gemini_model, len(contents))
        response = self._client.models.generate_content(
            model=gemini_model,
            contents=contents,
            config=config,
        )
        log.debug("Google AI response received")

        content = response.text or ""
        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count if usage else 0
        completion_tokens = usage.candidates_token_count if usage else 0

        log.debug("Google AI response length: %d chars", len(content))
        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.total_token_count if usage else 0,
            model=model,
            provider=self.provider_name,
        )
