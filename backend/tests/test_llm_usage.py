"""Tests for LLM usage tracking: model, repository, endpoint, and pipeline integration."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from repository.models import LLMUsageRecord
from services.llm.base import LLMResponse
from services.search import _calculate_cost, _log_llm_usage


# ── LLMUsageRecord model ────────────────────────────────────────────────────


class TestLLMUsageRecord:
    def test_default_fields(self):
        record = LLMUsageRecord()
        assert record.provider == ""
        assert record.model == ""
        assert record.operation == ""
        assert record.prompt_tokens == 0
        assert record.cost_usd == 0.0
        assert record.cache_hit is False
        assert record.batch_id is None
        assert record.user_id == ""
        assert record.record_id  # auto-generated UUID

    def test_to_dict(self):
        record = LLMUsageRecord(
            user_id="u1",
            provider="openrouter",
            model="google/gemini-2.5-flash",
            operation="label_reading",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.000155,
        )
        d = record.to_dict()
        assert d["provider"] == "openrouter"
        assert d["model"] == "google/gemini-2.5-flash"
        assert d["cost_usd"] == 0.000155
        assert d["user_id"] == "u1"

    def test_from_dict(self):
        data = {
            "record_id": "test-id",
            "timestamp": "2026-03-06T00:00:00Z",
            "user_id": "u1",
            "provider": "google",
            "model": "google/gemini-2.5-flash",
            "operation": "ranking",
            "prompt_tokens": 200,
            "completion_tokens": 80,
            "total_tokens": 280,
            "cost_usd": 0.00026,
            "batch_id": "batch-1",
            "item_id": "item-1",
            "cache_hit": False,
        }
        record = LLMUsageRecord.from_dict(data)
        assert record.record_id == "test-id"
        assert record.provider == "google"
        assert record.total_tokens == 280
        assert record.user_id == "u1"

    def test_roundtrip(self):
        record = LLMUsageRecord(
            user_id="u1",
            provider="openrouter",
            model="google/gemini-2.5-flash",
            operation="label_reading",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.000155,
        )
        d = record.to_dict()
        restored = LLMUsageRecord.from_dict(d)
        assert restored.provider == record.provider
        assert restored.cost_usd == record.cost_usd
        assert restored.user_id == record.user_id


# ── Cost calculation ─────────────────────────────────────────────────────────


class TestCostCalculation:
    def test_known_model(self):
        resp = LLMResponse(
            content="test",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            model="google/gemini-2.5-flash",
            provider="openrouter",
        )
        cost = _calculate_cost(resp)
        # 1000 * 0.30 / 1M + 500 * 2.50 / 1M = 0.0003 + 0.00125 = 0.00155
        assert abs(cost - 0.00155) < 1e-8

    def test_unknown_model_returns_zero(self):
        resp = LLMResponse(
            content="test",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            model="unknown/model",
            provider="openrouter",
        )
        assert _calculate_cost(resp) == 0.0


# ── _log_llm_usage ──────────────────────────────────────────────────────────


class TestLogLLMUsage:
    def test_skips_on_cache_hit(self):
        mock_repo = MagicMock()
        with patch("services.search.get_repo", return_value=mock_repo):
            _log_llm_usage("label_reading", LLMResponse(content="x"), cache_hit=True)
        mock_repo.save_llm_usage.assert_not_called()

    def test_skips_on_none_response(self):
        mock_repo = MagicMock()
        with patch("services.search.get_repo", return_value=mock_repo):
            _log_llm_usage("label_reading", None)
        mock_repo.save_llm_usage.assert_not_called()

    def test_saves_usage_record(self):
        mock_repo = MagicMock()
        resp = LLMResponse(
            content="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            model="google/gemini-2.5-flash",
            provider="openrouter",
        )
        with patch("services.search.get_repo", return_value=mock_repo):
            _log_llm_usage("label_reading", resp, batch_id="b1", item_id="i1", user_id="u1")

        mock_repo.save_llm_usage.assert_called_once()
        record = mock_repo.save_llm_usage.call_args[0][0]
        assert isinstance(record, LLMUsageRecord)
        assert record.operation == "label_reading"
        assert record.provider == "openrouter"
        assert record.batch_id == "b1"
        assert record.user_id == "u1"
        assert record.cache_hit is False

    def test_swallows_exceptions(self):
        """Usage logging failures should not crash the pipeline."""
        mock_repo = MagicMock()
        mock_repo.save_llm_usage.side_effect = RuntimeError("DB down")
        resp = LLMResponse(content="test", model="google/gemini-2.5-flash", provider="openrouter")
        with patch("services.search.get_repo", return_value=mock_repo):
            _log_llm_usage("label_reading", resp)  # Should not raise


# ── Usage endpoint ───────────────────────────────────────────────────────────


class TestUsageEndpoint:
    @pytest.fixture()
    def client(self, mock_jwt_user):
        from main import app
        from deps import get_repo

        mock_repo = MagicMock()
        app.dependency_overrides[get_repo] = lambda: mock_repo
        yield TestClient(app), mock_repo
        app.dependency_overrides.pop(get_repo, None)

    def test_get_usage_returns_summary(self, client):
        test_client, mock_repo = client
        summary = {
            "period_days": 30,
            "totals": {"total_calls": 10, "total_tokens": 5000, "total_cost_usd": 0.05},
            "by_day": [],
            "by_model": [],
            "by_operation": [],
        }
        mock_repo.get_usage_summary.return_value = summary

        resp = test_client.get("/api/usage")

        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == 30
        assert data["totals"]["total_calls"] == 10

    def test_get_usage_with_days_param(self, client):
        test_client, mock_repo = client
        mock_repo.get_usage_summary.return_value = {"period_days": 7, "totals": {}, "by_day": [], "by_model": [], "by_operation": []}

        resp = test_client.get("/api/usage?days=7")

        assert resp.status_code == 200
        mock_repo.get_usage_summary.assert_called_once_with("test-user-123", days=7)
