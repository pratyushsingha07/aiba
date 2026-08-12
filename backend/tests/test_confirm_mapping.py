"""
tests/test_confirm_mapping.py
──────────────────────────────
Integration tests for POST /confirm-mapping
"""
from __future__ import annotations

import io
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from tests.conftest import ORG_A_ID, USER_A_ID


def _upload_and_get_id(client: TestClient) -> str:
    """Helper: upload a valid file and return the upload_id."""
    buf = io.BytesIO()
    df = pd.DataFrame({
        "order_date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "revenue":    [1000.0, 2000.0, 1500.0],
        "Category":   ["Coding & Tech", "Coding & Tech", "K-12 Academics"],
        "Batch":      ["Batch A", "Batch A", "Batch B"],
        "Teacher":    ["Alice", "Alice", "Bob"],
        "State":      ["MH", "MH", "KA"],
        "order_id":   ["ORD001", "ORD002", "ORD003"],
    })
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sales", index=False)
    resp = client.post(
        "/api/v1/upload",
        files={"file": ("sales.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    return resp.json()["upload_id"]


class TestConfirmMapping:
    def test_confirm_mapping_returns_dataset_id(self, client: TestClient, token_org_a_admin: str):
        upload_id = _upload_and_get_id(client)
        resp = client.post(
            "/api/v1/confirm-mapping",
            json={
                "upload_id": upload_id,
                "mapping": {
                    "sales": {"Date": "order_date", "Sales": "revenue", "OrderID": "order_id"},
                    "refunds": {},
                    "targets": {},
                    "batches": {},
                },
            },
            headers={"Authorization": f"Bearer {token_org_a_admin}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "dataset_id" in body
        assert len(body["dataset_id"]) > 0

    def test_confirm_mapping_requires_auth(self, client: TestClient):
        resp = client.post(
            "/api/v1/confirm-mapping",
            json={"upload_id": str(uuid.uuid4()), "mapping": {}},
        )
        assert resp.status_code == 401

    def test_confirm_mapping_unknown_upload_id_returns_404(self, client: TestClient, token_org_a_admin: str):
        resp = client.post(
            "/api/v1/confirm-mapping",
            json={
                "upload_id": str(uuid.uuid4()),  # not in store
                "mapping": {"sales": {}, "refunds": {}, "targets": {}, "batches": {}},
            },
            headers={"Authorization": f"Bearer {token_org_a_admin}"},
        )
        assert resp.status_code == 404

    def test_confirm_mapping_blocking_validation_returns_422(self, client: TestClient, token_org_a_admin: str):
        """If the mapped data has ALL rows missing critical fields, return 422."""
        buf = io.BytesIO()
        # Data with no Date or Sales-like columns at all
        df = pd.DataFrame({"garbage_col": ["foo", "bar", "baz"]})
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Sales", index=False)
        upload_resp = client.post(
            "/api/v1/upload",
            files={"file": ("bad.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        upload_id = upload_resp.json()["upload_id"]

        confirm_resp = client.post(
            "/api/v1/confirm-mapping",
            json={
                "upload_id": upload_id,
                # Empty mapping — columns won't map to Date/Sales
                "mapping": {"sales": {}, "refunds": {}, "targets": {}, "batches": {}},
            },
            headers={"Authorization": f"Bearer {token_org_a_admin}"},
        )
        assert confirm_resp.status_code == 422
        body = confirm_resp.json()
        assert "validation_report" in body.get("detail", {})

    def test_confirm_mapping_evicts_pending_upload(self, client: TestClient, token_org_a_admin: str):
        """After a successful confirm, the upload_id should be invalid for reuse."""
        upload_id = _upload_and_get_id(client)
        client.post(
            "/api/v1/confirm-mapping",
            json={
                "upload_id": upload_id,
                "mapping": {"sales": {"Date": "order_date", "Sales": "revenue"}, "refunds": {}, "targets": {}, "batches": {}},
            },
            headers={"Authorization": f"Bearer {token_org_a_admin}"},
        )
        # Second confirm with the same upload_id should 404
        resp2 = client.post(
            "/api/v1/confirm-mapping",
            json={
                "upload_id": upload_id,
                "mapping": {"sales": {}, "refunds": {}, "targets": {}, "batches": {}},
            },
            headers={"Authorization": f"Bearer {token_org_a_admin}"},
        )
        assert resp2.status_code == 404
