"""
tests/test_grounding_validator.py
──────────────────────────────────
Unit tests for app/services/grounding_validator.py
"""
from __future__ import annotations

import pytest
from app.services.grounding_validator import validate_single_insight
from app.services.insight_engine import Insight

MOCK_KPI_DATA = {
    "scope": "category",
    "gross_revenue": 60000.0,
    "net_revenue": 57000.0,
    "refund_amount": 3000.0,
    "refund_percent": 5.0,
    "orders": 120,
    "average_selling_price": 500.0,
    "profit": 30000.0,
    "loss": 3000.0,
    "category_performance": [
        {
            "category": "Coding & Tech",
            "revenue": 60000.0,
            "orders": 120,
            "profit": 30000.0,
            "margin_used": 0.5,
            "is_default": False,
        }
    ],
    "batch_performance": [
        {
            "batch": "Batch A",
            "revenue": 60000.0,
            "admissions": 120,
            "capacity": 150,
            "fill_percent": 80.0,
            "capacity_missing": False,
            "profit": 27000.0,
            "refund_amount": 3000.0,
            "category": "Coding & Tech",
        }
    ],
    "mom_growth": None,
    "growth_data_scope": "unavailable_for_category",
    "total_target": None,
    "target_data_scope": "org_wide_only",
    "expected_month_revenue": None,
    "forecast_data_scope": "unavailable_for_category",
}


def test_grounded_insight_passes():
    """Insight with exact numbers from kpi_data should pass verification (verified=True)."""
    insight = Insight(
        insight="Gross revenue reached ₹60,000 across 120 orders with a net revenue of ₹57,000.",
        severity="info",
        supporting_kpi_ids=["gross_revenue", "orders", "net_revenue"],
        recommendation="Maintain current sales trajectory.",
        confidence=0.95,
    )
    res = validate_single_insight(insight, MOCK_KPI_DATA)
    assert res.verified is True
    assert res.unverified_reason is None


def test_wrong_number_fails_validation():
    """Insight citing a wrong number (e.g. ₹99,999 not in kpi_data) should be marked verified=False with 'number_mismatch'."""
    insight = Insight(
        insight="Gross revenue reached ₹99,999 across 120 orders.",
        severity="warning",
        supporting_kpi_ids=["gross_revenue"],
        recommendation="Investigate discrepancy.",
        confidence=0.8,
    )
    res = validate_single_insight(insight, MOCK_KPI_DATA)
    assert res.verified is False
    assert res.unverified_reason == "number_mismatch"


def test_referencing_null_scoped_field_fails_validation():
    """Insight citing a value for a field that is None (e.g. total_target) should fail with 'referenced_null_field'."""
    insight = Insight(
        insight="Total target was achieved at 95% with total_target set to 100000.",
        severity="critical",
        supporting_kpi_ids=["total_target"],
        recommendation="Adjust targets.",
        confidence=0.85,
    )
    res = validate_single_insight(insight, MOCK_KPI_DATA)
    assert res.verified is False
    assert res.unverified_reason == "referenced_null_field"
