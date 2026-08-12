"""
tests/test_upload.py
─────────────────────
Integration tests for POST /upload
"""
from __future__ import annotations

import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient


def _make_xlsx_bytes(data: dict | None = None) -> bytes:
    """Create a minimal in-memory xlsx file."""
    buf = io.BytesIO()
    df = pd.DataFrame(data or {
        "order_date": ["2026-01-01", "2026-01-02"],
        "revenue":    [1000.0,       2000.0],
        "Category":   ["Coding & Tech", "K-12 Academics"],
        "Batch":      ["Batch A",    "Batch B"],
        "Teacher":    ["Alice",      "Bob"],
        "State":      ["MH",         "KA"],
        "order_id":   ["ORD001",     "ORD002"],
    })
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sales", index=False)
    return buf.getvalue()


def _make_csv_bytes() -> bytes:
    return b"order_date,revenue,Category\n2026-01-01,1000,Coding & Tech\n"


class TestUpload:
    def test_upload_xlsx_returns_upload_id_and_preview(self, client: TestClient):
        xlsx = _make_xlsx_bytes()
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("sales.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "upload_id" in body
        assert "proposed_mapping" in body
        assert "validation_report" in body
        assert "sheet_preview" in body
        # upload_id should be a non-empty string
        assert len(body["upload_id"]) > 0

    def test_upload_csv_returns_upload_id(self, client: TestClient):
        csv_data = _make_csv_bytes()
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("sales.csv", csv_data, "text/csv")},
        )
        assert resp.status_code == 200
        assert "upload_id" in resp.json()

    def test_upload_proposes_mapping_for_aliased_columns(self, client: TestClient):
        """Columns like 'order_date' should be proposed as mapping for 'Date'."""
        xlsx = _make_xlsx_bytes()
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("sales.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        mapping = resp.json()["proposed_mapping"]
        # 'order_date' should map to 'Date' for the sales sheet
        assert mapping.get("sales", {}).get("Date") == "order_date"
        # 'revenue' should map to 'Sales'
        assert mapping.get("sales", {}).get("Sales") == "revenue"

    def test_upload_returns_validation_report(self, client: TestClient):
        xlsx = _make_xlsx_bytes()
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("sales.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        report = resp.json()["validation_report"]
        assert "is_valid" in report
        assert "total_rows" in report
        assert "errors" in report

    def test_upload_rejects_unsupported_extension(self, client: TestClient):
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("report.json", b'{"a":1}', "application/json")},
        )
        assert resp.status_code == 422

    def test_upload_rejects_empty_file(self, client: TestClient):
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("empty.xlsx", b"", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 422

    def test_upload_sheet_preview_max_10_rows(self, client: TestClient):
        """Preview should cap at 10 rows even if file has more."""
        data = {
            "order_date": [f"2026-01-{i:02d}" for i in range(1, 21)],
            "revenue":    [float(i * 100) for i in range(1, 21)],
        }
        xlsx = _make_xlsx_bytes(data)
        resp = client.post(
            "/api/v1/upload",
            files={"file": ("sales.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        preview = resp.json()["sheet_preview"]
        # All sheet previews should have at most 10 rows
        for sheet_rows in preview.values():
            assert len(sheet_rows) <= 10
