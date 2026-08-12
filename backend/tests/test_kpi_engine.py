from datetime import date
import pytest
import pandas as pd
from app.services.kpi_engine import calculate_kpis


# ─── Shared fixtures ─────────────────────────────────────────────────────────

def make_custom_margins():
    """Verified margins (is_default=False) for Coding & Tech and K-12 Academics."""
    return {
        "Coding & Tech":  {"margin": 0.60, "is_default": False},
        "K-12 Academics": {"margin": 0.30, "is_default": False},
    }


def make_sales_df():
    return pd.DataFrame([
        # Current month (August 2026)
        {"Date": "2026-08-10", "OrderID": "ORD-1", "Category": "Coding & Tech",  "Batch": "Batch A", "Teacher": "David", "State": "CA", "Sales": 200.0},
        {"Date": "2026-08-09", "OrderID": "ORD-2", "Category": "Coding & Tech",  "Batch": "Batch A", "Teacher": "David", "State": "CA", "Sales": 100.0},
        {"Date": "2026-08-01", "OrderID": "ORD-3", "Category": "K-12 Academics", "Batch": "Batch B", "Teacher": "Sarah", "State": "TX", "Sales": 300.0},
        # Previous month (July 2026)
        {"Date": "2026-07-15", "OrderID": "ORD-4", "Category": "Coding & Tech",  "Batch": "Batch A", "Teacher": "David", "State": "CA", "Sales": 400.0},
    ])


def make_refunds_df():
    return pd.DataFrame([
        {"Date": "2026-08-09", "OrderID": "ORD-2", "RefundAmount": 50.0,
         "Category": "Coding & Tech", "Batch": "Batch A", "Teacher": "David", "State": "CA"}
    ])


def make_batches_df():
    # Batch A has no Capacity row → capacity_missing expected
    return pd.DataFrame([
        {"Batch": "Batch B", "Capacity": 20, "Teacher": "Sarah", "Profit": None}
    ])


# ─── Test 1: Core KPIs + all 5 bug fixes ─────────────────────────────────────

def test_kpi_engine_basic_and_bug_fixes():
    ref_date = date(2026, 8, 10)

    res = calculate_kpis(
        sales_df=make_sales_df(),
        refunds_df=make_refunds_df(),
        targets_df=None,
        batches_df=make_batches_df(),
        category_margins=make_custom_margins(),
        reference_date=ref_date
    )

    # ── Base Revenue & Refund ─────────────────────────────────────────────────
    assert res["gross_revenue"] == 1000.0
    assert res["refund_amount"] == 50.0
    assert res["net_revenue"] == 950.0
    assert res["refund_percent"] == 5.0
    assert res["orders"] == 4

    # ── Bug Fix 1: System calendar Today / Yesterday ──────────────────────────
    assert res["today_sales"] == 200.0    # Aug 10
    assert res["yesterday_sales"] == 100.0  # Aug 9

    # ── Bug Fix 2: MoM equal-window (Aug 1-10 vs Jul 1-10) ───────────────────
    # Aug 1-10 sales = 200 + 100 + 300 = 600
    # Jul 1-10 sales = 0  (ORD-4 is Jul 15, outside the window)
    # → prev_month_sales == 0, so mom_growth == 0 (no prior window data)
    assert res["mom_growth"] == 0.0
    assert res["days_compared"] == 10

    # ── Bug Fix 3: Configurable profit margin per category ────────────────────
    # Coding & Tech  rev = 200 + 100 + 400 = 700 → 700 * 0.60 = 420
    # K-12 Academics rev = 300               → 300 * 0.30 =  90
    # Total profit = 510
    assert res["profit"] == 510.0

    # is_default flag per category entry
    cat_map = {c["category"]: c for c in res["category_performance"]}
    assert cat_map["Coding & Tech"]["is_default"] is False
    assert cat_map["K-12 Academics"]["is_default"] is False

    # ── Bug Fix 4: Missing target flag ───────────────────────────────────────
    assert res["target_data_missing"] is True
    assert res["total_target"] is None

    # ── Bug Fix 5: Missing batch capacity flag ────────────────────────────────
    batch_map = {b["batch"]: b for b in res["batch_performance"]}
    assert batch_map["Batch A"]["capacity_missing"] is True
    assert batch_map["Batch A"]["capacity"] is None
    assert batch_map["Batch B"]["capacity_missing"] is False
    assert batch_map["Batch B"]["capacity"] == 20


# ─── Test 2: Targets present ─────────────────────────────────────────────────

def test_kpi_engine_with_targets():
    ref_date = date(2026, 8, 10)
    sales_df = pd.DataFrame([
        {"Date": "2026-08-10", "OrderID": "ORD-1", "Category": "Coding & Tech", "Sales": 1000.0}
    ])
    targets_df = pd.DataFrame([
        {"Month": "2026-08", "Category": "Coding & Tech", "Target": 5000.0}
    ])

    res = calculate_kpis(
        sales_df=sales_df,
        targets_df=targets_df,
        reference_date=ref_date
    )

    assert res["target_data_missing"] is False
    assert res["total_target"] == 5000.0
    assert res["target_achieved_percent"] == 20.0
    assert res["target_remaining"] == 4000.0


# ─── Test 3: Mid-month MoM equal-window regression ───────────────────────────
# This test directly catches the original bug (comparing MTD vs full prior month).
# With ref_date = Aug 10:
#   • Current window: Aug 1–10  (10 days)
#   • Previous window: Jul 1–10 (10 days)   ← only these rows should count
#   • Jul 11–31 rows must be EXCLUDED from prev_month_sales

def test_mom_growth_equal_window_mid_month():
    ref_date = date(2026, 8, 10)

    rows = []
    # Aug 1–10: 10 rows × $100 = $1 000
    for day in range(1, 11):
        rows.append({
            "Date": f"2026-08-{day:02d}",
            "OrderID": f"AUG-{day:02d}",
            "Category": "Coding & Tech",
            "Sales": 100.0,
        })
    # Jul 1–10: 10 rows × $50 = $500  ← should be counted
    for day in range(1, 11):
        rows.append({
            "Date": f"2026-07-{day:02d}",
            "OrderID": f"JUL-EARLY-{day:02d}",
            "Category": "Coding & Tech",
            "Sales": 50.0,
        })
    # Jul 11–31: 21 rows × $100 = $2 100  ← must NOT be counted in prev window
    for day in range(11, 32):
        rows.append({
            "Date": f"2026-07-{day:02d}",
            "OrderID": f"JUL-LATE-{day:02d}",
            "Category": "Coding & Tech",
            "Sales": 100.0,
        })

    sales_df = pd.DataFrame(rows)
    res = calculate_kpis(sales_df=sales_df, reference_date=ref_date)

    # Equal-window: Aug 1-10 ($1 000) vs Jul 1-10 ($500)
    # MoM = (1000 - 500) / 500 * 100 = 100%
    assert res["mom_growth"] == 100.0
    assert res["days_compared"] == 10

    # Sanity check: if old logic (full Jul) were used, prev would be $500+$2100=$2600
    # and MoM would be ≈ -61.5% — opposite sign. The test would catch the regression.


# ─── Test 4: Default category margins carry is_default=True ─────────────────

def test_default_margins_flag():
    """When no custom margins are passed, unknown categories fall back to Default (is_default=True)."""
    sales_df = pd.DataFrame([
        {"Date": "2026-08-10", "OrderID": "ORD-1", "Category": "Robotics Club", "Sales": 500.0}
    ])
    res = calculate_kpis(sales_df=sales_df, reference_date=date(2026, 8, 10))

    cat_entry = res["category_performance"][0]
    assert cat_entry["category"] == "Robotics Club"
    # Falls back to Default margin → is_default must be True
    assert cat_entry["is_default"] is True
