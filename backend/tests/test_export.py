"""
tests/test_export.py
─────────────────────
Integration tests for GET /export/{dataset_id}?format=pdf|xlsx
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    DATASET_A_ID,
    mock_get_dataset,
    mock_get_snapshot,
)


class TestExport:
    def test_xlsx_export_returns_binary(self, client: TestClient, token_org_a_admin: str):
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/export/{DATASET_A_ID}?format=xlsx",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert len(resp.content) > 0
        # Verify it's a valid xlsx file (xlsx starts with PK zip magic bytes)
        assert resp.content[:2] == b"PK"

    def test_pdf_export_returns_binary(self, client: TestClient, token_org_a_admin: str):
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/export/{DATASET_A_ID}?format=pdf",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        # PDF magic bytes: %PDF
        assert resp.content[:4] == b"%PDF"

    def test_export_requires_auth(self, client: TestClient):
        resp = client.get(f"/api/v1/export/{DATASET_A_ID}?format=xlsx")
        assert resp.status_code == 401

    def test_export_cross_org_blocked(self, client: TestClient, token_org_b_analyst: str):
        """Org B user cannot export Org A's dataset."""
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/export/{DATASET_A_ID}?format=xlsx",
                headers={"Authorization": f"Bearer {token_org_b_analyst}"},
            )
        assert resp.status_code == 403

    def test_invalid_format_rejected(self, client: TestClient, token_org_a_admin: str):
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/export/{DATASET_A_ID}?format=csv",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert resp.status_code == 422

    def test_xlsx_has_content_disposition_header(self, client: TestClient, token_org_a_admin: str):
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_kpi_snapshot_by_dataset", side_effect=mock_get_snapshot):
            resp = client.get(
                f"/api/v1/export/{DATASET_A_ID}?format=xlsx",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert "content-disposition" in resp.headers
        assert "attachment" in resp.headers["content-disposition"]
