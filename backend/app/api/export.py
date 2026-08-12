"""
app/api/export.py
──────────────────
GET /export/{dataset_id}?format=pdf|xlsx

Auth required. Regenerates a formatted report from stored KPI data.
Does NOT re-run KPI calculations — uses the persisted kpi_json snapshot.

Mirrors the structure of js/exportManager.js:
  xlsx: 4 sheets — Summary KPIs / Category Performance / Batch Performance / Teacher & State
  pdf:  A4 reportlab document — title, generation date, KPI table, category/batch tables

Both are streamed as file downloads.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
import io

from app.core.auth import CurrentUser, get_current_user
from app.services.export_service import generate_pdf, generate_xlsx

router = APIRouter(tags=["export"])


@router.get("/export/{dataset_id}", status_code=status.HTTP_200_OK)
def export_dataset(
    dataset_id: str,
    format: str = Query(default="xlsx", regex="^(pdf|xlsx)$"),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream a formatted report (pdf or xlsx) for the requested dataset.
    Performs the same org-level access check as /dashboard.
    """
    # ── Fetch dataset + snapshot ──────────────────────────────────────────
    try:
        from app.db import models as db
        dataset = db.get_dataset(dataset_id)
    except RuntimeError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")

    # Defense-in-depth org check (RLS also enforces this at DB level)
    if dataset.get("org_id") != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    try:
        from app.db import models as db
        snapshot = db.get_kpi_snapshot_by_dataset(dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI snapshot not found.")

    kpi_json = snapshot.get("kpi_json", {})
    filename_base = dataset.get("filename", "report").rsplit(".", 1)[0]

    # ── Category filter for category_manager ─────────────────────────────
    # ⚠️ V1 LIMITATION: same app-layer filter as /dashboard
    if current_user.role == "category_manager" and current_user.assigned_category:
        from app.api.dashboard import _filter_kpi_by_category
        kpi_json = _filter_kpi_by_category(kpi_json, current_user.assigned_category)

    # ── Generate report ───────────────────────────────────────────────────
    if format == "xlsx":
        content = generate_xlsx(kpi_json, filename=filename_base)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        download_filename = f"{filename_base}_report.xlsx"
    else:  # pdf
        content = generate_pdf(kpi_json, filename=filename_base, dataset_meta=dataset)
        media_type = "application/pdf"
        download_filename = f"{filename_base}_report.pdf"

    return StreamingResponse(
        content=io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'},
    )
