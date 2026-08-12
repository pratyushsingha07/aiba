"""
tests/test_ask.py
──────────────────
Integration tests for POST /ask/{dataset_id} endpoint and rate limiting.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    DATASET_A_ID,
    mock_get_dataset,
    mock_get_snapshot,
)


class TestAskEndpoint:
    def test_ask_question_returns_grounded_answer(
        self, client: TestClient, token_org_a_admin: str, monkeypatch
    ):
        """Valid Q&A call using Claude should return verified answer."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
        from app.core.config import get_settings
        get_settings.cache_clear()

        mock_claude_response = MagicMock()
        mock_claude_response.content = [
            MagicMock(text="Gross revenue for the organization is ₹100,000 across 200 orders.")
        ]

        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot), \
             patch("app.db.models.get_user_usage_count_today", return_value=0), \
             patch("app.db.models.record_usage", return_value={}), \
             patch("anthropic.Anthropic") as mock_anthropic:

            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_claude_response
            mock_anthropic.return_value = mock_client

            resp = client.post(
                f"/api/v1/ask/{DATASET_A_ID}",
                json={"question": "What is our total revenue?"},
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["question"] == "What is our total revenue?"
        assert "100,000" in body["answer"]
        assert body["verified"] is True


    def test_ask_rate_limit_exceeded_returns_429(
        self, client: TestClient, token_org_a_admin: str
    ):
        """When user reaches 20 calls/day, return HTTP 429 Too Many Requests."""
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot), \
             patch("app.db.models.get_user_usage_count_today", return_value=20):

            resp = client.post(
                f"/api/v1/ask/{DATASET_A_ID}",
                json={"question": "Why did sales drop?"},
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )

        assert resp.status_code == 429
        assert "Daily Q&A rate limit exceeded" in resp.json()["detail"]
