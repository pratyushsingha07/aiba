"""
app/api/upload.py
──────────────────
POST /upload

Preview-only step — no permanent storage, no KPI computation.

Flow:
  1. Accept multipart .xlsx / .csv file
  2. Read all sheets via read_sheets_from_file()
  3. Auto-detect sheet types via auto_detect_sheet_types()
  4. Run propose_column_mapping() per sheet type
  5. Run validate_sales_dataframe() on the detected sales sheet (using proposed column names)
  6. Store raw bytes + DataFrames + proposed mapping in UploadStore (keyed by UUID, 1-hour TTL)
  7. Return: { upload_id, proposed_mapping, validation_report, sheet_preview }

Auth: NOT required — the upload step is a browser-side preview. Auth is required at confirm-mapping.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, status

from app.core.upload_store import PendingUpload, create_upload_id, pending_store
from app.services.data_parser import (
    EXPECTED_COLUMNS,
    auto_detect_sheet_types,
    propose_column_mapping,
    read_sheets_from_file,
)
from app.services.validation import validate_sales_dataframe

router = APIRouter(tags=["upload"])

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def _df_preview(df: pd.DataFrame, n: int = 10) -> List[Dict[str, Any]]:
    """Return the first n rows of a DataFrame as JSON-safe dicts."""
    preview = df.head(n).copy()
    # Replace NaN with None for JSON serialisation
    preview = preview.where(pd.notnull(preview), other=None)
    return preview.to_dict(orient="records")


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Accept a multipart .xlsx/.csv file, run column-mapping proposals and
    initial validation, and return a short-lived upload_id for the confirm step.
    Does NOT save anything permanently.
    """
    # ── Validate file extension ───────────────────────────────────────────────
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # ── Read bytes ────────────────────────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 50 MB limit.")

    # ── Parse sheets ──────────────────────────────────────────────────────────
    try:
        raw_sheets = read_sheets_from_file(file_bytes, filename)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse file: {exc}",
        ) from exc

    sheet_dfs = auto_detect_sheet_types(raw_sheets)

    # ── Propose column mappings per sheet type ────────────────────────────────
    proposed_mapping: Dict[str, Dict[str, Optional[str]]] = {}
    for sheet_type, expected_cols in EXPECTED_COLUMNS.items():
        df = sheet_dfs.get(sheet_type, pd.DataFrame())
        headers = list(df.columns) if not df.empty else []
        proposed_mapping[sheet_type] = propose_column_mapping(headers, expected_cols)

    # ── Validate sales sheet with proposed mapping ────────────────────────────
    sales_df = sheet_dfs.get("sales", pd.DataFrame())
    sales_mapping = proposed_mapping.get("sales", {})

    # Temporarily rename columns using the proposed mapping for validation
    renamed_sales = sales_df.copy()
    if not renamed_sales.empty:
        rename_map = {v: k for k, v in sales_mapping.items() if v is not None and v in renamed_sales.columns}
        renamed_sales.rename(columns=rename_map, inplace=True)

    validation_report = validate_sales_dataframe(renamed_sales)

    # ── Store in upload store ─────────────────────────────────────────────────
    upload_id = create_upload_id()
    pending = PendingUpload(
        upload_id=upload_id,
        filename=filename,
        file_bytes=file_bytes,
        sheet_dfs=sheet_dfs,
        proposed_mapping=proposed_mapping,
    )
    pending_store.put(pending)

    # ── Build preview (first 10 rows per detected sheet) ─────────────────────
    sheet_preview: Dict[str, Any] = {}
    for sheet_type, df in sheet_dfs.items():
        if not df.empty:
            sheet_preview[sheet_type] = _df_preview(df, n=10)

    return {
        "upload_id": upload_id,
        "proposed_mapping": proposed_mapping,
        "validation_report": validation_report.model_dump(),
        "sheet_preview": sheet_preview,
    }
