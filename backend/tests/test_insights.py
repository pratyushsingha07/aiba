"""
tests/test_insights.py
───────────────────────
Integration tests for POST /insights/{dataset_id} and caching logic.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    DATASET_A_ID,
    MOCK_KPI_JSON,
    mock_get_dataset,
    mock_get_snapshot,
)
from app.services.insight_engine import Insight


@pytest.fixture
def mock_llm_insights():
    return [
        Insight(
            insight="Gross revenue reached ₹60,000 across 120 orders.",
            severity="info",
            supporting_kpi_ids=["gross_revenue", "orders"],
            recommendation="Continue current marketing strategy.",
            confidence=0.9,
        )
    ]


class TestInsightsEndpoint:
    def test_category_manager_insights_use_category_scoped_data(
        self, client: TestClient, token_category_manager: str, mock_llm_insights
    ):
        """category_manager calling /insights should receive insights grounded in category data (scope: category)."""
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot), \
             patch("app.db.models.get_cached_insights", return_value=None), \
             patch("app.db.models.create_insight_cache_entry", return_value={}), \
             patch("app.api.insights.generate_insights", return_value=mock_llm_insights) as mock_gen:

            resp = client.post(
                f"/api/v1/insights/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_category_manager}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["scope"] == "category"
        assert len(body["insights"]) == 1
        assert body["insights"][0]["verified"] is True

        # Check prompt payload sent to generator
        passed_kpi = mock_gen.call_args.kwargs["kpi_data"]
        assert passed_kpi["gross_revenue"] == 60000.0  # Category revenue, NOT org total 100000
        assert passed_kpi["scope"] == "category"

    def test_insights_caching_behavior(
        self, client: TestClient, token_org_a_admin: str, mock_llm_insights
    ):
        """Second call with identical dataset_id and scope uses cached response without calling LLM."""
        cached_entry = {
            "provider_used": "groq",
            "insights_json": [mock_llm_insights[0].model_dump()],
        }

        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot), \
             patch("app.db.models.get_cached_insights", return_value=cached_entry), \
             patch("app.api.insights.generate_insights") as mock_gen:

            resp = client.post(
                f"/api/v1/insights/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["cached"] is True
        assert mock_gen.call_count == 0  # LLM was NOT called
