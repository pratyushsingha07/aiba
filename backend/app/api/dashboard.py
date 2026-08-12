"""
app/api/dashboard.py
─────────────────────
GET /dashboard/{dataset_id}

Auth required. Returns stored kpi_json for the requested dataset.

Multi-tenancy enforcement (defense-in-depth):
  1. RLS on kpi_snapshots (via datasets join) ensures the Supabase query
     cannot return rows from another org — this is the hard DB-level boundary.
  2. We ALSO explicitly verify dataset.org_id == current_user.org_id in app code
     before returning anything. This is intentional defense-in-depth, not redundant.
  3. category_manager role: kpi_json is filtered at the app layer to only include
     the user's assigned_category, and top-level aggregate KPIs are recomputed or
     nulled out with explicit scope flags so org-level metrics are never exposed.

⚠️  V1 LIMITATION — JSONB category isolation:
     Postgres RLS cannot filter *inside* the kpi_json JSONB blob. Category-level
     restriction is enforced entirely at the app layer below. A category_manager with
     direct API access (e.g. using curl with their token, bypassing the UI) could
     theoretically see other categories' data if this app-layer filter has a bug.
     Resolution in v2: store per-category KPI rows in a separate materialized table with
     a proper org_id + category FK that Postgres RLS can enforce natively.
"""
from __future__ import annotations

import copy
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user

router = APIRouter(tags=["dashboard"])


def _filter_kpi_by_category(kpi_json: Dict[str, Any], category: str) -> Dict[str, Any]:
    """
    App-layer category filter and aggregate recomputation for category_manager role.

    1. Filters category_performance and batch_performance arrays down to the assigned category.
    2. Recomputes top-level revenue/orders/profit/refund metrics from the filtered category data.
    3. Sets metrics that require raw time-series / targets / forecast data to null with explicit
       scope flags (*_scope) so org-level totals are never leaked.
    4. Sets "scope": "category".
    """
    filtered = copy.deepcopy(kpi_json)

    # ── 1. Filter breakdown arrays ───────────────────────────────────────────
    cat_entries = [
        entry for entry in filtered.get("category_performance", [])
        if entry.get("category") == category
    ]
    filtered["category_performance"] = cat_entries

    filtered["batch_performance"] = [
        entry for entry in filtered.get("batch_performance", [])
        if entry.get("category") == category
    ]

    # ── 2. Top-level Scope Identifier ─────────────────────────────────────────
    filtered["scope"] = "category"

    # ── 3. Recompute or Null Aggregate Fields ─────────────────────────────────
    if cat_entries:
        cat_info = cat_entries[0]

        # gross_revenue: Recomputed from category revenue (gross revenue for this category)
        # Note: category_performance revenue is gross revenue before refunds
        cat_rev = float(cat_info.get("revenue", 0.0))
        cat_orders = int(cat_info.get("orders", 0))
        cat_profit = float(cat_info.get("profit", 0.0))

        # Sum refund amounts from filtered batches belonging to this category
        cat_refund_amount = sum(
            float(b.get("refund_amount", 0.0))
            for b in filtered["batch_performance"]
        )

        cat_net_revenue = max(0.0, cat_rev - cat_refund_amount)
        cat_refund_percent = float((cat_refund_amount / cat_rev) * 100.0) if cat_rev > 0 else 0.0
        cat_asp = float(cat_rev / cat_orders) if cat_orders > 0 else 0.0

        filtered["gross_revenue"] = round(cat_rev, 2)
        filtered["net_revenue"] = round(cat_net_revenue, 2)
        filtered["refund_amount"] = round(cat_refund_amount, 2)
        filtered["refund_percent"] = round(cat_refund_percent, 2)
        filtered["orders"] = cat_orders
        filtered["average_selling_price"] = round(cat_asp, 2)
        filtered["profit"] = round(cat_profit, 2)
        filtered["loss"] = round(cat_refund_amount, 2)
    else:
        # User assigned to a category not present in dataset
        filtered["gross_revenue"] = 0.0
        filtered["net_revenue"] = 0.0
        filtered["refund_amount"] = 0.0
        filtered["refund_percent"] = 0.0
        filtered["orders"] = 0
        filtered["average_selling_price"] = 0.0
        filtered["profit"] = 0.0
        filtered["loss"] = 0.0

    # ── Field-by-Field Justifications for Nulled / Scoped Metrics ─────────────

    # today_sales / yesterday_sales / daily_run_rate:
    # Requires date-wise raw transaction breakdown for this specific category.
    # Nulled out to prevent leaking org-wide daily velocity or inferring other categories' daily sales.
    filtered["today_sales"] = None
    filtered["yesterday_sales"] = None
    filtered["daily_run_rate"] = None

    # wow_growth / mom_growth:
    # Requires historical equal-window transaction rows per category which are not stored in kpi_json.
    # Nulled out with growth_data_scope flag so frontend displays "growth unavailable per-category".
    filtered["wow_growth"] = None
    filtered["mom_growth"] = None
    filtered["growth_data_scope"] = "unavailable_for_category"

    # target_* metrics:
    # Targets in current schema are org-wide or not broken down in kpi_json.
    # Nulled out with target_data_scope flag to inform frontend that targets are org-wide only.
    filtered["total_target"] = None
    filtered["target_achieved_percent"] = None
    filtered["target_remaining"] = None
    filtered["required_drr"] = None
    filtered["target_data_scope"] = "org_wide_only"

    # forecast / expected_month_revenue:
    # Forecast requires daily run rate and category targets, neither of which are isolatable from kpi_json alone.
    # Nulled out with forecast_data_scope flag.
    filtered["expected_month_revenue"] = None
    filtered["forecast_target_achievement"] = None
    filtered["forecast_data_scope"] = "unavailable_for_category"

    return filtered


@router.get("/dashboard/{dataset_id}", status_code=status.HTTP_200_OK)
def get_dashboard(
    dataset_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return stored KPI data for a dataset.
    Enforces org isolation at app layer AND relies on DB-level RLS.
    Applies category-level filtering and aggregate recomputation for category_manager users.
    """
    # ── Fetch dataset metadata ────────────────────────────────────────────
    try:
        from app.db import models as db
        dataset = db.get_dataset(dataset_id)
    except RuntimeError:
        # Supabase not configured (test mode) — raise 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found.")

    # ── Defense-in-depth: explicit org check in app code ─────────────────
    # RLS also enforces this at the DB level, but we check here too so that
    # any RLS misconfiguration does not silently expose cross-org data.
    if dataset.get("org_id") != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this dataset.",
        )

    # ── Fetch KPI snapshot ────────────────────────────────────────────────
    try:
        from app.db import models as db
        snapshot = db.get_kpi_snapshot_by_dataset(dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KPI snapshot not found for this dataset.",
        )

    kpi_json = snapshot.get("kpi_json", {})

    # ── Category-level app-layer filter (category_manager only) ──────────
    if current_user.role == "category_manager" and current_user.assigned_category:
        kpi_json = _filter_kpi_by_category(kpi_json, current_user.assigned_category)
    else:
        # Full org view for admin, business_head, analyst
        kpi_json = copy.deepcopy(kpi_json)
        kpi_json["scope"] = "org"

    return {
        "dataset_id": dataset_id,
        "filename": dataset.get("filename"),
        "uploaded_at": dataset.get("uploaded_at"),
        "kpi_data": kpi_json,
    }

