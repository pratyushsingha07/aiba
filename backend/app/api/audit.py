"""
app/api/audit.py
─────────────────
GET /audit/{dataset_id}

Auth required, same org check as /dashboard.
Returns audit_log entries tied to the dataset, structured so the frontend can
show "why this number is what it is" for each KPI.

Each audit entry contains:
  - action: e.g. "upload_confirmed"
  - created_at
  - user_id
  - details.mapping_applied:       the column mapping the user approved
  - details.non_blocking_warnings: validation warnings (duplicates, negative sales)
  - details.default_margins_used:  which category margins were estimates vs verified
  - details.validation_summary:    count of each error type
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user

router = APIRouter(tags=["audit"])


@router.get("/audit/{dataset_id}", status_code=status.HTTP_200_OK)
def get_audit(
    dataset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return the audit trail for a dataset.
    Enforces org isolation: same defense-in-depth org check as /dashboard.
    """
    # ── Fetch dataset metadata for org check ─────────────────────────────
    try:
        from app.db import models as db
        dataset = db.get_dataset(dataset_id)
    except RuntimeError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")

    # Defense-in-depth org check
    if dataset.get("org_id") != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this dataset's audit log.",
        )

    # ── Fetch audit entries ───────────────────────────────────────────────
    try:
        from app.db import models as db
        entries = db.get_audit_entries_for_dataset(dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # ── Shape entries for frontend "why is this number what it is" ────────
    shaped: List[Dict[str, Any]] = []
    for entry in entries:
        details = entry.get("details") or {}
        shaped.append({
            "audit_id":               entry.get("id"),
            "action":                 entry.get("action"),
            "performed_by":           entry.get("user_id"),
            "timestamp":              entry.get("created_at"),
            "column_mapping_used":    details.get("mapping_applied", {}),
            "validation_warnings":    details.get("non_blocking_warnings", []),
            "default_margins_applied": details.get("default_margins_used", {}),
            "validation_summary":     details.get("validation_summary", {}),
            "raw_details":            details,  # full details for debugging
        })

    return {
        "dataset_id": dataset_id,
        "filename":   dataset.get("filename"),
        "audit_log":  shaped,
    }
