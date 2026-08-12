import pytest
from app.services.data_parser import propose_column_mapping, EXPECTED_COLUMNS

def test_propose_column_mapping_exact_and_alias_matches():
    headers = ["order date", "order_id", "course category", "group", "mentor", "location", "gross revenue", "students"]
    target_fields = EXPECTED_COLUMNS["sales"]
    
    proposed = propose_column_mapping(headers, target_fields)
    
    assert proposed["Date"] == "order date"
    assert proposed["OrderID"] == "order_id"
    assert proposed["Category"] == "course category"
    assert proposed["Batch"] == "group"
    assert proposed["Teacher"] == "mentor"
    assert proposed["State"] == "location"
    assert proposed["Sales"] == "gross revenue"
    assert proposed["Admissions"] == "students"

def test_propose_column_mapping_unmatched_headers():
    headers = ["random_col_1", "random_col_2"]
    target_fields = ["Date", "Sales"]
    
    proposed = propose_column_mapping(headers, target_fields)
    
    assert proposed["Date"] is None
    assert proposed["Sales"] is None
