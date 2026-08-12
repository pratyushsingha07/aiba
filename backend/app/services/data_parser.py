import io
import re
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

EXPECTED_COLUMNS = {
    "sales": ["Date", "OrderID", "Category", "Batch", "Teacher", "State", "Sales", "Admissions"],
    "refunds": ["Date", "OrderID", "RefundAmount", "Category", "Batch", "Teacher", "State"],
    "targets": ["Month", "Category", "Target"],
    "batches": ["Batch", "Capacity", "Teacher", "Profit"]
}

COLUMN_ALIASES = {
    "Date": ["date", "order date", "transaction date", "day", "time"],
    "OrderID": ["order id", "order_id", "transaction id", "id", "invoice"],
    "Category": ["category", "course category", "stream", "dept", "department"],
    "Batch": ["batch", "batch name", "course", "class", "group"],
    "Teacher": ["teacher", "instructor", "faculty", "mentor", "trainer"],
    "State": ["state", "region", "location", "city", "province"],
    "Sales": ["sales", "revenue", "amount", "price", "sales amount", "total", "gross revenue"],
    "Admissions": ["admissions", "enrollments", "students", "quantity", "qty", "count"],
    "RefundAmount": ["refundamount", "refund amount", "refunded", "refunded amount", "refund"],
    "Month": ["month", "target month", "period", "year-month"],
    "Target": ["target", "monthly target", "goal", "quota"],
    "Capacity": ["capacity", "max seats", "seats", "total seats"],
    "Profit": ["profit", "margin", "net profit", "earnings"]
}

def clean_header(header: str) -> str:
    """Normalize string by lowercasing and removing spaces/underscores/hyphens."""
    if not isinstance(header, str):
        header = str(header)
    return re.sub(r'[\s_\-]', '', header.lower().strip())

def propose_column_mapping(headers: List[str], target_fields: List[str]) -> Dict[str, Optional[str]]:
    """
    Given a list of column headers from an uploaded file/sheet and target system fields,
    returns a proposed mapping dictionary: { system_field_name: matched_user_header_or_None }.

    Strategy (two-pass to avoid ambiguous substring grabs):
      Pass 1 — exact alias match: cleaned_header == cleaned_alias
      Pass 2 — substring match:   cleaned_alias in cleaned_header
    Headers that are already assigned to a field are not re-used.
    """
    mapping: Dict[str, Optional[str]] = {}
    cleaned_pairs = [(h, clean_header(h)) for h in headers]
    used_headers: set = set()

    # Pass 1: exact alias matches
    for field in target_fields:
        aliases = COLUMN_ALIASES.get(field, [field.lower()])
        cleaned_aliases = [clean_header(a) for a in aliases]
        for orig_header, ch in cleaned_pairs:
            if orig_header in used_headers:
                continue
            if any(ch == ca for ca in cleaned_aliases):
                mapping[field] = orig_header
                used_headers.add(orig_header)
                break

    # Pass 2: substring matches for fields still unmatched
    for field in target_fields:
        if field in mapping:
            continue
        aliases = COLUMN_ALIASES.get(field, [field.lower()])
        cleaned_aliases = [clean_header(a) for a in aliases]
        for orig_header, ch in cleaned_pairs:
            if orig_header in used_headers:
                continue
            if any(ca in ch for ca in cleaned_aliases):
                mapping[field] = orig_header
                used_headers.add(orig_header)
                break
        else:
            mapping.setdefault(field, None)

    # Ensure all requested fields appear in the result (even if None)
    for field in target_fields:
        mapping.setdefault(field, None)

    return mapping

def read_sheets_from_file(file_bytes: bytes, filename: str) -> Dict[str, pd.DataFrame]:
    """
    Reads an Excel or CSV file into a dictionary of sheet_name -> DataFrame.
    For CSV, returns a single key 'sales' or sheet name from filename.
    """
    sheets: Dict[str, pd.DataFrame] = {}
    if filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
        sheets["sales"] = df
    else:
        excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            sheets[sheet_name] = df
    return sheets

def auto_detect_sheet_types(sheets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Identifies sheet types (sales, refunds, targets, batches) based on sheet names or fallback.
    """
    categorized: Dict[str, pd.DataFrame] = {
        "sales": pd.DataFrame(),
        "refunds": pd.DataFrame(),
        "targets": pd.DataFrame(),
        "batches": pd.DataFrame()
    }
    
    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        lower_name = sheet_name.lower()
        if "sale" in lower_name or "transaction" in lower_name:
            categorized["sales"] = df
        elif "refund" in lower_name:
            categorized["refunds"] = df
        elif "target" in lower_name:
            categorized["targets"] = df
        elif "batch" in lower_name or "course" in lower_name:
            categorized["batches"] = df
            
    # Fallback if only 1 sheet uploaded and no category matched
    if categorized["sales"].empty and len(sheets) == 1:
        categorized["sales"] = list(sheets.values())[0]
        
    return categorized
