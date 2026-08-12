"""
app/api/insights.py
────────────────────
POST /insights/{dataset_id}

Auth required. Returns grounded AI insights for the dataset.
Uses same org + category scoping as GET /dashboard/{dataset_id}.
Caches results in insight_cache table keyed by (dataset_id, scope, kpi_hash).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dashboard import get_dashboard
from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.services.grounding_validator import validate_grounding
from app.services.insight_engine import generate_insights

router = APIRouter(tags=["insights"])


def _hash_payload(payload: Dict[str, Any]) -> str:
    """Return SHA256 hex digest of a JSON-serializable dictionary."""
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@router.post("/insights/{dataset_id}", status_code=status.HTTP_200_OK)
def get_dataset_insights(
    dataset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generate or return cached grounded AI insights for a dataset.
    Uses exact scoped KPI payload from GET /dashboard logic.
    """
    # ── Fetch scoped dashboard data ───────────────────────────────────────
    dashboard_res = get_dashboard(dataset_id=dataset_id, current_user=current_user)
    kpi_data = dashboard_res.get("kpi_data", {})
    scope = kpi_data.get("scope", "org")

    kpi_hash = _hash_payload(kpi_data)
    settings = get_settings()

    # ── Check Cache ───────────────────────────────────────────────────────
    try:
        from app.db import models as db
        cached = db.get_cached_insights(dataset_id=dataset_id, scope=scope, kpi_hash=kpi_hash)
        if cached:
            return {
                "dataset_id": dataset_id,
                "scope": scope,
                "cached": True,
                "provider_used": cached.get("provider_used"),
                "insights": cached.get("insights_json"),
            }
    except Exception:
        pass  # Fall through if DB/cache not initialized (e.g. test mode)

    # ── Generate Insights ─────────────────────────────────────────────────
    provider = settings.insight_provider
    try:
        raw_insights = generate_insights(kpi_data=kpi_data, scope=scope, provider=provider)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate insights: {exc}",
        ) from exc

    # ── Validate Grounding ────────────────────────────────────────────────
    validated_insights = validate_grounding(
        insights=raw_insights,
        kpi_data=kpi_data,
        org_id=current_user.org_id,
        user_id=current_user.user_id,
        dataset_id=dataset_id,
    )
    insights_json = [i.model_dump() for i in validated_insights]

    # ── Store in Cache ────────────────────────────────────────────────────
    try:
        from app.db import models as db
        db.create_insight_cache_entry(
            dataset_id=dataset_id,
            scope=scope,
            kpi_hash=kpi_hash,
            insights_json=insights_json,
            provider_used=provider,
        )
    except Exception:
        pass

    return {
        "dataset_id": dataset_id,
        "scope": scope,
        "cached": False,
        "provider_used": provider,
        "insights": insights_json,
    }
