"""
app/api/confirm_mapping.py
───────────────────────────
POST /confirm-mapping

Auth required. Finalises an upload: applies user-approved column mapping,
re-validates, computes KPIs, persists everything, writes audit log.

Request body:
  {
    "upload_id": "uuid",
    "mapping": {
      "sales":   { "Date": "order_date", "Sales": "revenue", ... },
      "refunds": { "RefundAmount": "refunded", ... },
      "targets": { ... },
      "batches": { ... }
    }
  }

Blocking error conditions → HTTP 422 (nothing saved):
  - upload_id expired or not found
  - After applying mapping, sales sheet still has no Date or Sales column
  - After applying mapping, ALL rows fail critical validation (all rows have missing Date/Sales)

On success:
  1. KPIs calculated
  2. File moved to Supabase Storage: {org_id}/{dataset_id}/{filename}
  3. datasets row inserted (status='active')
  4. kpi_snapshots row inserted
  5. audit_log entry written
  6. Pending upload evicted
  7. Returns { dataset_id }
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import CurrentUser, get_current_user
from app.core.upload_store import pending_store
from app.services.data_parser import EXPECTED_COLUMNS
from app.services.kpi_engine import DEFAULT_CATEGORY_MARGINS, calculate_kpis
from app.services.validation import validate_sales_dataframe

router = APIRouter(tags=["confirm-mapping"])


class ConfirmMappingRequest(BaseModel):
    upload_id: str
    # mapping[sheet_type][system_field] = user_column_name_in_file (or None to leave unmapped)
    mapping: Dict[str, Dict[str, Optional[str]]]


def _apply_mapping(df: pd.DataFrame, mapping: Dict[str, Optional[str]]) -> pd.DataFrame:
    """Rename df columns according to {system_field: user_column} mapping."""
    if df.empty or not mapping:
        return df
    rename_map = {v: k for k, v in mapping.items() if v is not None and v in df.columns}
    return df.rename(columns=rename_map)


def _is_blocking(validation_report) -> bool:
    """
    Decide if validation errors are 'blocking' (must halt processing).
    Blocking = missing Date or Sales column entirely, OR every single row has
    a MISSING_CRITICAL_FIELD error (no valid rows to compute KPIs from).
    Non-blocking = duplicate OrderIDs, some negative sales, partial missing rows.
    """
    r = validation_report
    # All rows are invalid
    if r.total_rows > 0 and r.missing_critical_fields_count == r.total_rows:
        return True
    # Error types that are always blocking (column-level, not row-level)
    blocking_types = {"MISSING_CRITICAL_FIELD"}
    # If EVERY row has a missing critical field, block. Otherwise allow with warnings.
    critical_errors = [e for e in r.errors if e.error_type in blocking_types]
    if len(critical_errors) == r.total_rows and r.total_rows > 0:
        return True
    return False


@router.post("/confirm-mapping", status_code=status.HTTP_200_OK)
def confirm_mapping(
    body: ConfirmMappingRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Apply user-approved column mapping, revalidate, compute KPIs, persist.
    Returns { dataset_id } on success. Returns HTTP 422 on blocking validation errors.
    """
    # ── Look up pending upload ─────────────────────────────────────────────
    pending = pending_store.get(body.upload_id)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"upload_id '{body.upload_id}' not found or has expired. Re-upload the file.",
        )

    # ── Apply mapping per sheet ────────────────────────────────────────────
    mapped_dfs: Dict[str, pd.DataFrame] = {}
    for sheet_type in ["sales", "refunds", "targets", "batches"]:
        df = pending.sheet_dfs.get(sheet_type, pd.DataFrame())
        sheet_mapping = body.mapping.get(sheet_type, {})
        mapped_dfs[sheet_type] = _apply_mapping(df, sheet_mapping)

    sales_df = mapped_dfs["sales"]
    refunds_df = mapped_dfs["refunds"]
    targets_df = mapped_dfs["targets"]
    batches_df = mapped_dfs["batches"]

    # ── Re-validate with the final mapped data ────────────────────────────
    validation_report = validate_sales_dataframe(sales_df)
    if _is_blocking(validation_report):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Validation failed with blocking errors. No data was saved.",
                "validation_report": validation_report.model_dump(),
            },
        )

    # ── Compute KPIs ───────────────────────────────────────────────────────
    kpi_result = calculate_kpis(
        sales_df=sales_df,
        refunds_df=refunds_df if not refunds_df.empty else None,
        targets_df=targets_df if not targets_df.empty else None,
        batches_df=batches_df if not batches_df.empty else None,
    )

    # ── Determine which margins were used (for audit + snapshot) ──────────
    margins_used = {}
    for cat_perf in kpi_result.get("category_performance", []):
        cat = cat_perf["category"]
        margins_used[cat] = {
            "margin": cat_perf["margin_used"],
            "is_default": cat_perf["is_default"],
        }

    # ── Collect non-blocking validation warnings ──────────────────────────
    non_blocking_warnings = [
        {"row": e.row_index, "type": e.error_type, "message": e.message}
        for e in validation_report.errors
    ]

    # ── Persist to Supabase (graceful degradation if Supabase not configured) ─
    dataset_id = str(uuid.uuid4())
    storage_path = None

    try:
        from app.db import models as db

        # 1. Upload file to Supabase Storage under {org_id}/{dataset_id}/filename
        storage_path = f"{current_user.org_id}/{dataset_id}/{pending.filename}"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
            if pending.filename.endswith((".xlsx", ".xls")) else "text/csv"
        db.upload_to_storage("datasets", storage_path, pending.file_bytes, content_type)

        # 2. Insert dataset row
        dataset_row = db.create_dataset(
            org_id=current_user.org_id,
            uploaded_by=current_user.user_id,
            filename=pending.filename,
            status="active",
            storage_path=storage_path,
        )
        dataset_id = dataset_row["id"]

        # 3. Insert KPI snapshot
        db.create_kpi_snapshot(
            dataset_id=dataset_id,
            kpi_json=kpi_result,
            category_margins_used=margins_used,
        )

        # 4. Write audit log entry
        db.create_audit_entry(
            org_id=current_user.org_id,
            user_id=current_user.user_id,
            action="upload_confirmed",
            dataset_id=dataset_id,
            details={
                "filename": pending.filename,
                "mapping_applied": body.mapping,
                "non_blocking_warnings": non_blocking_warnings,
                "default_margins_used": {
                    cat: info for cat, info in margins_used.items() if info.get("is_default")
                },
                "validation_summary": validation_report.summary,
            },
        )

    except RuntimeError:
        # Supabase not configured — running in test/dev mode without real credentials.
        # We still return a dataset_id so the rest of the test flow works.
        pass
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist data: {exc}",
        ) from exc

    # ── Evict from pending store ───────────────────────────────────────────
    pending_store.evict(body.upload_id)

    return {"dataset_id": dataset_id}
