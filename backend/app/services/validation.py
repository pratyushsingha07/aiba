from typing import Dict, List, Any
import pandas as pd
from pydantic import BaseModel

class ValidationError(BaseModel):
    row_index: int
    error_type: str
    message: str
    invalid_data: Dict[str, Any]

class ValidationReport(BaseModel):
    is_valid: bool
    total_rows: int
    duplicate_order_ids: List[str]
    negative_sales_count: int
    missing_critical_fields_count: int
    errors: List[ValidationError]
    summary: Dict[str, int]

def validate_sales_dataframe(df: pd.DataFrame, date_col: str = "Date", order_id_col: str = "OrderID", sales_col: str = "Sales") -> ValidationReport:
    """
    Validates sales dataframe for:
    - Missing critical fields (Date, Sales)
    - Negative Sales values
    - Duplicate OrderIDs
    """
    errors: List[ValidationError] = []
    duplicate_order_ids: List[str] = []
    negative_sales_count = 0
    missing_critical_fields_count = 0
    
    if df.empty:
        return ValidationReport(
            is_valid=True,
            total_rows=0,
            duplicate_order_ids=[],
            negative_sales_count=0,
            missing_critical_fields_count=0,
            errors=[],
            summary={"total_errors": 0}
        )
        
    total_rows = len(df)
    
    # 1. Check duplicate OrderIDs
    if order_id_col in df.columns:
        order_counts = df[order_id_col].dropna().astype(str).value_counts()
        duplicates = order_counts[order_counts > 1].index.tolist()
        duplicate_order_ids = duplicates
        
        for dup_id in duplicates:
            dup_rows = df[df[order_id_col].astype(str) == dup_id]
            for idx in dup_rows.index:
                row_dict = df.loc[idx].to_dict()
                # sanitize NaN for JSON compatibility
                sanitized_dict = {k: (None if pd.isna(v) else v) for k, v in row_dict.items()}
                errors.append(ValidationError(
                    row_index=int(idx),
                    error_type="DUPLICATE_ORDER_ID",
                    message=f"Duplicate OrderID '{dup_id}' detected.",
                    invalid_data=sanitized_dict
                ))

    # 2. Check each row for missing critical fields and negative sales
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        sanitized_dict = {k: (None if pd.isna(v) else v) for k, v in row_dict.items()}
        
        # Missing Date or Sales
        has_missing_date = (date_col not in df.columns) or pd.isna(row.get(date_col)) or str(row.get(date_col)).strip() == ""
        has_missing_sales = (sales_col not in df.columns) or pd.isna(row.get(sales_col))
        
        if has_missing_date or has_missing_sales:
            missing_fields = []
            if has_missing_date:
                missing_fields.append(date_col)
            if has_missing_sales:
                missing_fields.append(sales_col)
            
            missing_critical_fields_count += 1
            errors.append(ValidationError(
                row_index=int(idx),
                error_type="MISSING_CRITICAL_FIELD",
                message=f"Row is missing required critical field(s): {', '.join(missing_fields)}.",
                invalid_data=sanitized_dict
            ))
            
        # Negative Sales
        if sales_col in df.columns and not pd.isna(row.get(sales_col)):
            try:
                val = float(row.get(sales_col))
                if val < 0:
                    negative_sales_count += 1
                    errors.append(ValidationError(
                        row_index=int(idx),
                        error_type="NEGATIVE_SALES",
                        message=f"Sales value cannot be negative ({val}).",
                        invalid_data=sanitized_dict
                    ))
            except (ValueError, TypeError):
                pass
                
    summary = {
        "duplicate_order_id_errors": len(duplicate_order_ids),
        "negative_sales_errors": negative_sales_count,
        "missing_critical_field_errors": missing_critical_fields_count,
        "total_errors": len(errors)
    }
    
    is_valid = (len(errors) == 0)
    
    return ValidationReport(
        is_valid=is_valid,
        total_rows=total_rows,
        duplicate_order_ids=duplicate_order_ids,
        negative_sales_count=negative_sales_count,
        missing_critical_fields_count=missing_critical_fields_count,
        errors=errors,
        summary=summary
    )
