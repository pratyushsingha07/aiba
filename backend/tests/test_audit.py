"""
tests/test_audit.py
────────────────────
Integration tests for GET /audit/{dataset_id}
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    DATASET_A_ID,
    mock_get_dataset,
    mock_get_audit,
)


class TestAudit:
    def test_audit_returns_structured_entries(self, client: TestClient, token_org_a_admin: str):
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_audit_entries_for_dataset", side_effect=mock_get_audit):
            resp = client.get(
                f"/api/v1/audit/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "audit_log" in body
        assert "dataset_id" in body
        entries = body["audit_log"]
        assert len(entries) >= 1

        # Verify the structure has the fields needed for "why is this number what it is"
        first = entries[0]
        assert "action" in first
        assert "column_mapping_used" in first
        assert "validation_warnings" in first
        assert "default_margins_applied" in first
        assert "validation_summary" in first

    def test_audit_requires_auth(self, client: TestClient):
        resp = client.get(f"/api/v1/audit/{DATASET_A_ID}")
        assert resp.status_code == 401

    def test_audit_cross_org_blocked(self, client: TestClient, token_org_b_analyst: str):
        """Org B user cannot see Org A dataset's audit log."""
        with patch("app.db.models.get_dataset", side_effect=mock_get_dataset), \
             patch("app.db.models.get_audit_entries_for_dataset", side_effect=mock_get_audit):
            resp = client.get(
                f"/api/v1/audit/{DATASET_A_ID}",
                headers={"Authorization": f"Bearer {token_org_b_analyst}"},
            )
        assert resp.status_code == 403

    def test_audit_not_found(self, client: TestClient, token_org_a_admin: str):
        with patch("app.db.models.get_dataset", return_value=None):
            resp = client.get(
                "/api/v1/audit/00000000-0000-0000-0000-000000000000",
                headers={"Authorization": f"Bearer {token_org_a_admin}"},
            )
        assert resp.status_code == 404
