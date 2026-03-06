"""Tests for the LLM provider abstraction layer."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.llm.base import LLMResponse
from services.llm.openrouter import OpenRouterProvider
from services.llm.factory import get_llm_client


# ── LLMResponse ──────────────────────────────────────────────────────────────


class TestLLMResponse:
    def test_default_fields(self):
        resp = LLMResponse(content="hello")
        assert resp.content == "hello"
        assert resp.prompt_tokens == 0
        assert resp.completion_tokens == 0
        assert resp.total_tokens == 0
        assert resp.model == ""
        assert resp.provider == ""

    def test_all_fields(self):
        resp = LLMResponse(
            content="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            model="google/gemini-2.5-flash",
            provider="openrouter",
        )
        assert resp.total_tokens == 150
        assert resp.model == "google/gemini-2.5-flash"


# ── OpenRouterProvider ───────────────────────────────────────────────────────


class TestOpenRouterProvider:
    def test_chat_returns_llm_response(self):
        provider = OpenRouterProvider(api_key="test-key", base_url="https://test.api/chat")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value"}'}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("services.llm.openrouter.requests.post", return_value=mock_resp) as mock_post:
            result = provider.chat(
                [{"role": "user", "content": "test"}],
                model="google/gemini-2.5-flash",
            )

        assert isinstance(result, LLMResponse)
        assert result.content == '{"key": "value"}'
        assert result.prompt_tokens == 200
        assert result.completion_tokens == 80
        assert result.total_tokens == 280
        assert result.model == "google/gemini-2.5-flash"
        assert result.provider == "openrouter"

        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["model"] == "google/gemini-2.5-flash"

    def test_chat_handles_missing_usage(self):
        provider = OpenRouterProvider(api_key="test-key", base_url="https://test.api/chat")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hello"}}],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("services.llm.openrouter.requests.post", return_value=mock_resp):
            result = provider.chat([{"role": "user", "content": "test"}], model="test-model")

        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0

    def test_provider_name(self):
        provider = OpenRouterProvider(api_key="key", base_url="url")
        assert provider.provider_name == "openrouter"


# ── GoogleAIProvider ─────────────────────────────────────────────────────────


class TestGoogleAIProvider:
    def test_chat_returns_llm_response(self):
        mock_genai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"albums": ["Test"]}'
        mock_response.usage_metadata.prompt_token_count = 150
        mock_response.usage_metadata.candidates_token_count = 60
        mock_genai_client.models.generate_content.return_value = mock_response

        with patch("services.llm.google_ai.genai.Client", return_value=mock_genai_client):
            from services.llm.google_ai import GoogleAIProvider
            provider = GoogleAIProvider(api_key="test-key")

        result = provider.chat(
            [{"role": "user", "content": "test"}],
            model="google/gemini-2.5-flash",
        )

        assert isinstance(result, LLMResponse)
        assert result.content == '{"albums": ["Test"]}'
        assert result.prompt_tokens == 150
        assert result.completion_tokens == 60
        assert result.total_tokens == 210
        assert result.provider == "google"

    def test_strips_google_prefix_from_model(self):
        mock_genai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_genai_client.models.generate_content.return_value = mock_response

        with patch("services.llm.google_ai.genai.Client", return_value=mock_genai_client):
            from services.llm.google_ai import GoogleAIProvider
            provider = GoogleAIProvider(api_key="test-key")

        provider.chat([{"role": "user", "content": "test"}], model="google/gemini-2.5-flash")

        call_kwargs = mock_genai_client.models.generate_content.call_args
        assert call_kwargs[1]["model"] == "gemini-2.5-flash"

    def test_provider_name(self):
        mock_genai_client = MagicMock()
        with patch("services.llm.google_ai.genai.Client", return_value=mock_genai_client):
            from services.llm.google_ai import GoogleAIProvider
            provider = GoogleAIProvider(api_key="test-key")
        assert provider.provider_name == "google"

    def test_system_message_sets_instruction(self):
        mock_genai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_genai_client.models.generate_content.return_value = mock_response

        with patch("services.llm.google_ai.genai.Client", return_value=mock_genai_client):
            from services.llm.google_ai import GoogleAIProvider
            provider = GoogleAIProvider(api_key="test-key")

        provider.chat(
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "hello"},
            ],
            model="gemini-2.5-flash",
        )

        call_kwargs = mock_genai_client.models.generate_content.call_args
        config = call_kwargs[1]["config"]
        assert config.system_instruction == "You are a helpful assistant."

    def test_system_message_non_string_content_ignored(self):
        from services.llm.google_ai import _translate_messages

        contents, system_instruction = _translate_messages([
            {"role": "system", "content": [{"type": "text", "text": "sys"}]},
            {"role": "user", "content": "hello"},
        ])
        assert system_instruction is None
        assert len(contents) == 1

    def test_multipart_image_content(self):
        import base64
        from services.llm.google_ai import _translate_messages

        fake_image = base64.b64encode(b"fake-jpeg").decode()
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "What is this?"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{fake_image}"}},
            ]},
        ]
        contents, system_instruction = _translate_messages(messages)
        assert len(contents) == 1
        assert len(contents[0].parts) == 2

    def test_multipart_image_url_non_data_uri(self):
        from services.llm.google_ai import _translate_messages

        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe"},
                {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
            ]},
        ]
        contents, _ = _translate_messages(messages)
        assert len(contents[0].parts) == 2

    def test_assistant_role_mapped_to_model(self):
        from services.llm.google_ai import _translate_messages

        contents, _ = _translate_messages([
            {"role": "assistant", "content": "I can help with that."},
            {"role": "user", "content": "thanks"},
        ])
        assert contents[0].role == "model"
        assert contents[1].role == "user"


# ── Factory ──────────────────────────────────────────────────────────────────


class TestFactory:
    def test_default_is_openrouter(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        client = get_llm_client()
        assert client.provider_name == "openrouter"

    def test_openrouter_explicit(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        client = get_llm_client()
        assert client.provider_name == "openrouter"

    def test_google_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "google")
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "test-key")
        with patch("services.llm.google_ai.genai.Client"):
            client = get_llm_client()
        assert client.provider_name == "google"

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "unknown")
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            get_llm_client()
