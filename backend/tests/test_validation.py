import pytest
import pandas as pd
from app.services.validation import validate_sales_dataframe

def test_validation_clean_data():
    df = pd.DataFrame([
        {"Date": "2026-08-10", "OrderID": "ORD-1", "Sales": 100},
        {"Date": "2026-08-10", "OrderID": "ORD-2", "Sales": 200}
    ])
    report = validate_sales_dataframe(df)
    assert report.is_valid is True
    assert report.total_rows == 2
    assert report.summary["total_errors"] == 0

def test_validation_duplicates_negatives_missing():
    df = pd.DataFrame([
        {"Date": "2026-08-10", "OrderID": "ORD-1", "Sales": 100},
        {"Date": "2026-08-10", "OrderID": "ORD-1", "Sales": -50}, # Duplicate OrderID & Negative Sales
        {"Date": None, "OrderID": "ORD-3", "Sales": None}          # Missing Date & Sales
    ])
    report = validate_sales_dataframe(df)
    assert report.is_valid is False
    assert "ORD-1" in report.duplicate_order_ids
    assert report.negative_sales_count == 1
    assert report.missing_critical_fields_count == 1
    assert len(report.errors) > 0
