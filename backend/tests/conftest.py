"""
tests/conftest.py
──────────────────
Shared pytest fixtures for Phase 2 integration tests.

Design principles:
  - NO real Supabase calls — all DB/Storage interactions are mocked.
  - Fake JWTs are signed with TEST_JWT_SECRET (overrides settings via env var).
  - Three token fixtures: org_a_admin, org_b_analyst, category_manager_coding.
  - The FastAPI TestClient is set up with the app's dependency overrides
    so we don't need to mock at the module level.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

# ── Constants ─────────────────────────────────────────────────────────────────
TEST_JWT_SECRET = "test-secret-for-pytest-only"
TEST_JWT_ALGO = "HS256"

ORG_A_ID = str(uuid.uuid4())
ORG_B_ID = str(uuid.uuid4())

USER_A_ID = str(uuid.uuid4())
USER_B_ID = str(uuid.uuid4())
USER_CAT_MGR_ID = str(uuid.uuid4())

DATASET_A_ID = str(uuid.uuid4())
DATASET_B_ID = str(uuid.uuid4())


# ── JWT helper ────────────────────────────────────────────────────────────────

def make_token(
    user_id: str,
    org_id: str,
    role: str = "analyst",
    assigned_category: Optional[str] = None,
    secret: str = TEST_JWT_SECRET,
    expired: bool = False,
) -> str:
    exp = datetime.now(timezone.utc) + (
        timedelta(hours=-1) if expired else timedelta(hours=1)
    )
    payload = {
        "sub": user_id,
        "exp": exp,
        "app_metadata": {
            "org_id": org_id,
            "role": role,
            "assigned_category": assigned_category,
        },
    }
    return jwt.encode(payload, secret, algorithm=TEST_JWT_ALGO)


# ── Token fixtures ────────────────────────────────────────────────────────────

@pytest.fixture()
def token_org_a_admin() -> str:
    return make_token(USER_A_ID, ORG_A_ID, role="admin")


@pytest.fixture()
def token_org_b_analyst() -> str:
    return make_token(USER_B_ID, ORG_B_ID, role="analyst")


@pytest.fixture()
def token_category_manager() -> str:
    """Category manager in Org A, assigned to 'Coding & Tech'."""
    return make_token(
        USER_CAT_MGR_ID, ORG_A_ID,
        role="category_manager",
        assigned_category="Coding & Tech",
    )


@pytest.fixture()
def token_expired() -> str:
    return make_token(USER_A_ID, ORG_A_ID, expired=True)


# ── App & Client fixture ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_jwt_secret(monkeypatch):
    """Override JWT_SECRET so tests use TEST_JWT_SECRET."""
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SUPABASE_URL", "")        # disable real Supabase
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "")
    # Clear lru_cache so Settings re-reads env vars
    from app.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    from main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Mock DB data ──────────────────────────────────────────────────────────────

MOCK_KPI_JSON: Dict[str, Any] = {
    "gross_revenue": 100000.0,
    "net_revenue": 95000.0,
    "refund_amount": 5000.0,
    "refund_percent": 5.0,
    "orders": 200,
    "average_selling_price": 500.0,
    "today_sales": 1200.0,
    "yesterday_sales": 1100.0,
    "daily_run_rate": 3333.33,
    "wow_growth": 5.5,
    "mom_growth": 10.2,
    "days_compared": 11,
    "target_data_missing": True,
    "total_target": None,
    "target_achieved_percent": None,
    "target_remaining": None,
    "required_drr": None,
    "expected_month_revenue": None,
    "forecast_target_achievement": None,
    "profit": 42000.0,
    "loss": 5000.0,
    "category_performance": [
        {"category": "Coding & Tech", "revenue": 60000.0, "orders": 120, "profit": 30000.0, "margin_used": 0.5, "is_default": False},
        {"category": "K-12 Academics", "revenue": 40000.0, "orders": 80,  "profit": 16000.0, "margin_used": 0.4, "is_default": False},
    ],
    "batch_performance": [
        {"batch": "Batch A", "revenue": 60000.0, "admissions": 120, "capacity": 150, "fill_percent": 80.0, "capacity_missing": False, "profit": 27000.0, "refund_amount": 3000.0, "category": "Coding & Tech"},
        {"batch": "Batch B", "revenue": 40000.0, "admissions": 80,  "capacity": None, "fill_percent": None, "capacity_missing": True, "profit": 16000.0, "refund_amount": 2000.0, "category": "K-12 Academics"},
    ],
    "teacher_performance": [
        {"teacher": "Alice", "revenue": 70000.0, "admissions": 140},
        {"teacher": "Bob",   "revenue": 30000.0, "admissions": 60},
    ],
    "state_performance": [
        {"state": "Maharashtra", "revenue": 80000.0},
        {"state": "Karnataka",   "revenue": 20000.0},
    ],
}

MOCK_DATASET_A: Dict[str, Any] = {
    "id": DATASET_A_ID,
    "org_id": ORG_A_ID,
    "uploaded_by": USER_A_ID,
    "filename": "sales_test.xlsx",
    "storage_path": f"{ORG_A_ID}/{DATASET_A_ID}/sales_test.xlsx",
    "uploaded_at": "2026-08-01T10:00:00+00:00",
    "status": "active",
}

MOCK_DATASET_B: Dict[str, Any] = {
    "id": DATASET_B_ID,
    "org_id": ORG_B_ID,
    "uploaded_by": USER_B_ID,
    "filename": "sales_orgb.xlsx",
    "storage_path": f"{ORG_B_ID}/{DATASET_B_ID}/sales_orgb.xlsx",
    "uploaded_at": "2026-08-01T11:00:00+00:00",
    "status": "active",
}

MOCK_SNAPSHOT_A: Dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "dataset_id": DATASET_A_ID,
    "kpi_json": MOCK_KPI_JSON,
    "category_margins_used": {"Coding & Tech": {"margin": 0.5, "is_default": False}},
    "created_at": "2026-08-01T10:05:00+00:00",
}

MOCK_AUDIT_ENTRIES = [
    {
        "id": str(uuid.uuid4()),
        "org_id": ORG_A_ID,
        "user_id": USER_A_ID,
        "dataset_id": DATASET_A_ID,
        "action": "upload_confirmed",
        "created_at": "2026-08-01T10:05:00+00:00",
        "details": {
            "filename": "sales_test.xlsx",
            "mapping_applied": {"sales": {"Date": "order_date", "Sales": "revenue"}},
            "non_blocking_warnings": [],
            "default_margins_used": {},
            "validation_summary": {"total_errors": 0},
        },
    }
]


def mock_get_dataset(dataset_id: str):
    """Return mock dataset based on ID."""
    if dataset_id == DATASET_A_ID:
        return MOCK_DATASET_A
    if dataset_id == DATASET_B_ID:
        return MOCK_DATASET_B
    return None


def mock_get_snapshot(dataset_id: str):
    if dataset_id == DATASET_A_ID:
        return MOCK_SNAPSHOT_A
    return None


def mock_get_audit(dataset_id: str):
    if dataset_id == DATASET_A_ID:
        return MOCK_AUDIT_ENTRIES
    return []
