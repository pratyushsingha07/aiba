"""
tests/test_dashboard.py
────────────────────────
Integration tests for GET /dashboard/{dataset_id}

Critical tests:
  1. test_cross_org_blocked     — Org B user requesting Org A dataset → 403
  2. test_category_manager_filter — category_manager sees only their category
  3. test_auth_required          — no token → 401
  4. test_expired_token_rejected — expired token → 401
  5. test_dataset_not_found      — invalid UUID → 404
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    DATASET_A_ID,
    DATASET_B_ID,
    MOCK_DATASET_A,
    MOCK_DATASET_B,
    MOCK_SNAPSHOT_A,
    mock_get_dataset,
    mock_get_snapshot,
)


class TestDashboard:

    # ── Auth tests ────────────────────────────────────────────────────────────

    def test_auth_required(self, client: TestClient):
        """No token → 401."""
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(f"/api/v1/dashboard/{DATASET_A_ID}")
        assert resp.status_code == 401

    def test_expired_token_rejected(self, client: TestClient, token_expired: str):
        """Expired JWT → 401."""
        resp = client.get(
            f"/api/v1/dashboard/{DATASET_A_ID}",
            headers={"Authorization": f"Bearer {token_expired}"},
        )
        assert resp.status_code == 401

    # ── Cross-org isolation (CRITICAL) ───────────────────────────────────────

    def test_cross_org_blocked(self, client: TestClient, token_org_b_analyst: str):
        """
        CRITICAL: Org B user requests Org A's dataset_id → must get 403, NOT the data.
        This test proves cross-org isolation at the app layer (defense-in-depth).
        DB-level RLS would also block this in production.
        """
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            # Org B token requesting Org A's dataset
            resp = client.get(
                f"/api/v1/dashboard/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_org_b_analyst}"},
            )

        # Must be 403 Forbidden — not 200, not the KPI data
        assert resp.status_code == 403, (
            f"SECURITY FAILURE: Org B user got {resp.status_code} "
            f"on Org A's dataset. Response: {resp.text}"
        )

    def test_org_a_can_access_own_dataset(self, client: TestClient, token_org_a_admin: str):
        """Positive case: Org A user can read Org A's dataset."""
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/dashboard/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "kpi_data" in body
        assert body["kpi_data"]["gross_revenue"] == 100000.0

    # ── Category filter & scoping tests (CRITICAL) ─────────────────────────────

    def test_category_manager_filter(self, client: TestClient, token_category_manager: str):
        """
        CRITICAL: category_manager assigned to 'Coding & Tech' should ONLY see
        'Coding & Tech' in category_performance. 'K-12 Academics' must be absent.
        """
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/dashboard/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_category_manager}"},
            )

        assert resp.status_code == 200
        cat_perf = resp.json()["kpi_data"]["category_performance"]

        # Must contain exactly one entry: Coding & Tech
        categories_returned = [row["category"] for row in cat_perf]
        assert "Coding & Tech" in categories_returned, \
            "category_manager's own category should be visible"
        assert "K-12 Academics" not in categories_returned, (
            "FILTER FAILURE: category_manager can see a category they are not assigned to. "
            "App-layer filter in dashboard.py is broken."
        )

    def test_category_manager_batch_filter(self, client: TestClient, token_category_manager: str):
        """Batch performance should also be filtered to assigned category."""
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/dashboard/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_category_manager}"},
            )
        assert resp.status_code == 200
        batch_perf = resp.json()["kpi_data"]["batch_performance"]
        # Only batches with category == "Coding & Tech" should appear
        batch_categories = [b.get("category") for b in batch_perf]
        for cat in batch_categories:
            assert cat == "Coding & Tech", \
                f"Batch with category '{cat}' leaked through category filter"

    def test_category_manager_recomputed_aggregates_and_scope_flags(self, client: TestClient, token_category_manager: str):
        """
        CRITICAL: Aggregate top-level metrics for category_manager must be recomputed from their
        category data, NOT the org-wide total. Un-recomputable metrics must be nulled with scope flags.
        """
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/dashboard/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_category_manager}"},
            )
        assert resp.status_code == 200
        kpi = resp.json()["kpi_data"]

        # Scope flag
        assert kpi.get("scope") == "category"

        # Recomputed aggregate metrics for 'Coding & Tech'
        # In MOCK_KPI_JSON:
        # Coding & Tech: revenue = 60000.0, orders = 120, profit = 30000.0
        # Batch A (Coding & Tech): refund_amount = 3000.0
        # Net revenue = 60000 - 3000 = 57000.0
        assert kpi["gross_revenue"] == 60000.0, "gross_revenue must match Coding & Tech revenue, not org total 100000"
        assert kpi["net_revenue"] == 57000.0, "net_revenue must be 57000, not org total 95000"
        assert kpi["refund_amount"] == 3000.0, "refund_amount must be 3000 for Coding & Tech, not org total 5000"
        assert kpi["orders"] == 120, "orders must be 120, not org total 200"
        assert kpi["profit"] == 30000.0, "profit must be 30000, not org total 42000"
        assert kpi["loss"] == 3000.0

        # Un-recomputable fields must be NULLED with scope flags (not equal to org totals)
        assert kpi["mom_growth"] is None
        assert kpi["wow_growth"] is None
        assert kpi["growth_data_scope"] == "unavailable_for_category"

        assert kpi["total_target"] is None
        assert kpi["target_achieved_percent"] is None
        assert kpi["target_data_scope"] == "org_wide_only"

        assert kpi["expected_month_revenue"] is None
        assert kpi["forecast_data_scope"] == "unavailable_for_category"

    def test_admin_sees_all_categories_and_org_scope(self, client: TestClient, token_org_a_admin: str):
        """Admin role should NOT have category filtering applied and scope should be 'org'."""
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/dashboard/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert resp.status_code == 200
        kpi = resp.json()["kpi_data"]
        assert kpi.get("scope") == "org"
        assert kpi["gross_revenue"] == 100000.0
        assert kpi["net_revenue"] == 95000.0

        cat_perf = kpi["category_performance"]
        categories = [row["category"] for row in cat_perf]
        assert "Coding & Tech" in categories
        assert "K-12 Academics" in categories

    # ── Not found ─────────────────────────────────────────────────────────────

    def test_dataset_not_found(self, client: TestClient, token_org_a_admin: str):
        """Non-existent dataset_id → 404."""
        with patch("app.db.models.get_dataset", return_value=None):
            resp = client.get(
                "/api/v1/dashboard/00000000-0000-0000-0000-000000000000",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert resp.status_code == 404

