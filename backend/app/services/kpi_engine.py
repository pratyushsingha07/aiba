from datetime import date, datetime, timedelta
import calendar
from typing import Dict, List, Optional, Any
import pandas as pd

# Each entry: {"margin": float, "is_default": bool}
# is_default=True means this is a placeholder estimate, not a verified figure.
DEFAULT_CATEGORY_MARGINS = {
    "Coding & Tech":     {"margin": 0.50, "is_default": False},
    "K-12 Academics":    {"margin": 0.40, "is_default": False},
    "Creative Arts":     {"margin": 0.45, "is_default": True},
    "Language Learning": {"margin": 0.35, "is_default": True},
    "Default":           {"margin": 0.45, "is_default": True},
}

def calculate_kpis(
    sales_df: pd.DataFrame,
    refunds_df: Optional[pd.DataFrame] = None,
    targets_df: Optional[pd.DataFrame] = None,
    batches_df: Optional[pd.DataFrame] = None,
    category_margins: Optional[Dict[str, Dict]] = None,
    reference_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Computes all core business KPIs, entity breakdowns, and forecasts.
    Fixes key bugs:
    1. Today & Yesterday use real calendar system dates (or injectable reference_date).
    2. MoM growth uses an equal-window comparison: days 1–days_passed of current month vs
       days 1–days_passed of the previous month. Output includes `days_compared` (the window size).
    3. Profit margins are configurable per category via {"margin": float, "is_default": bool} dicts.
    4. Missing target data returns `target_data_missing: true` (no fabricated target).
    5. Missing batch capacity flags `capacity_missing: true` (no default to 50).
    """
    if category_margins is None:
        category_margins = DEFAULT_CATEGORY_MARGINS

    ref_date = reference_date if reference_date else date.today()
    yesterday_date = ref_date - timedelta(days=1)

    # Standardize Sales DataFrame
    sales = sales_df.copy() if (sales_df is not None and not sales_df.empty) else pd.DataFrame(columns=["Date", "Sales", "Category", "Batch", "Teacher", "State", "OrderID"])
    if "Date" in sales.columns and not sales.empty:
        sales["Date_parsed"] = pd.to_datetime(sales["Date"], errors="coerce").dt.date
    else:
        sales["Date_parsed"] = pd.Series(dtype="object")

    if "Sales" in sales.columns:
        sales["Sales"] = pd.to_numeric(sales["Sales"], errors="coerce").fillna(0.0)
    else:
        sales["Sales"] = 0.0

    # Standardize Refunds DataFrame
    refunds = refunds_df.copy() if (refunds_df is not None and not refunds_df.empty) else pd.DataFrame(columns=["Date", "RefundAmount", "Category", "Batch", "Teacher", "State"])
    if "RefundAmount" in refunds.columns:
        refunds["RefundAmount"] = pd.to_numeric(refunds["RefundAmount"], errors="coerce").fillna(0.0)
    else:
        refunds["RefundAmount"] = 0.0

    # 1. Base Revenue & Order Metrics
    gross_revenue = float(sales["Sales"].sum()) if not sales.empty else 0.0
    refund_amount = float(refunds["RefundAmount"].sum()) if not refunds.empty else 0.0
    net_revenue = max(0.0, gross_revenue - refund_amount)
    refund_percent = float((refund_amount / gross_revenue) * 100.0) if gross_revenue > 0 else 0.0
    total_orders = len(sales)
    average_selling_price = float(gross_revenue / total_orders) if total_orders > 0 else 0.0

    # 2. System Calendar Date Today & Yesterday Sales
    today_sales = float(sales[sales["Date_parsed"] == ref_date]["Sales"].sum()) if not sales.empty else 0.0
    yesterday_sales = float(sales[sales["Date_parsed"] == yesterday_date]["Sales"].sum()) if not sales.empty else 0.0

    # 3. Daily Run Rate (DRR) over dataset's actual date span
    valid_dates = sales["Date_parsed"].dropna().unique()
    if len(valid_dates) > 0:
        min_d = min(valid_dates)
        max_d = max(valid_dates)
        days_in_period = max(1, (max_d - min_d).days + 1)
    else:
        days_in_period = 1
    daily_run_rate = float(gross_revenue / days_in_period)

    # 4. WoW Growth (last 7 days vs previous 7 days relative to ref_date or latest date)
    wow_anchor = ref_date if ref_date in valid_dates else (max(valid_dates) if len(valid_dates) > 0 else ref_date)
    last_7_start = wow_anchor - timedelta(days=6)
    prev_7_start = wow_anchor - timedelta(days=13)
    prev_7_end = wow_anchor - timedelta(days=7)

    last_7_sales = float(sales[(sales["Date_parsed"] >= last_7_start) & (sales["Date_parsed"] <= wow_anchor)]["Sales"].sum()) if not sales.empty else 0.0
    prev_7_sales = float(sales[(sales["Date_parsed"] >= prev_7_start) & (sales["Date_parsed"] <= prev_7_end)]["Sales"].sum()) if not sales.empty else 0.0

    wow_growth = float(((last_7_sales - prev_7_sales) / prev_7_sales) * 100.0) if prev_7_sales > 0 else 0.0

    # 5. MoM Growth — equal-window comparison
    # Compare days 1..days_passed of the current month vs days 1..days_passed of the previous month.
    # e.g. if today is Aug 10, compare Aug 1-10 vs Jul 1-10 (not the full July).
    current_year = ref_date.year
    current_month = ref_date.month
    days_passed = ref_date.day  # e.g. 10 on Aug 10

    if current_month == 1:
        prev_month = 12
        prev_month_year = current_year - 1
    else:
        prev_month = current_month - 1
        prev_month_year = current_year

    def is_in_month_window(d_val, year, month, day_limit):
        """True if date is within days 1..day_limit of the given month/year."""
        return (
            d_val is not None
            and d_val.year == year
            and d_val.month == month
            and d_val.day <= day_limit
        )

    current_month_sales = float(
        sales[sales["Date_parsed"].apply(
            lambda d: is_in_month_window(d, current_year, current_month, days_passed)
        )]["Sales"].sum()
    ) if not sales.empty else 0.0

    prev_month_sales = float(
        sales[sales["Date_parsed"].apply(
            lambda d: is_in_month_window(d, prev_month_year, prev_month, days_passed)
        )]["Sales"].sum()
    ) if not sales.empty else 0.0

    mom_growth = float(((current_month_sales - prev_month_sales) / prev_month_sales) * 100.0) if prev_month_sales > 0 else 0.0
    days_compared = days_passed  # window size for both months

    # 6. Targets Data & Forecasting
    target_data_missing = (targets_df is None or targets_df.empty or "Target" not in targets_df.columns)
    
    if target_data_missing:
        total_target = None
        target_achieved_percent = None
        target_remaining = None
        required_drr = None
        expected_month_revenue = None
        forecast_target_achievement = None
    else:
        targets_df_clean = targets_df.copy()
        targets_df_clean["Target"] = pd.to_numeric(targets_df_clean["Target"], errors="coerce").fillna(0.0)
        total_target = float(targets_df_clean["Target"].sum())

        target_achieved_percent = float((gross_revenue / total_target) * 100.0) if total_target > 0 else 0.0
        target_remaining = float(max(0.0, total_target - gross_revenue))

        # Days in month based on ref_date
        _, days_in_month = calendar.monthrange(ref_date.year, ref_date.month)
        days_passed = ref_date.day
        days_remaining = max(1, days_in_month - days_passed)

        required_drr = float(target_remaining / days_remaining)
        expected_month_revenue = float(daily_run_rate * days_in_month)
        forecast_target_achievement = float((expected_month_revenue / total_target) * 100.0) if total_target > 0 else 0.0

    # 7. Category Performance & Configurable Profit Margins
    _fallback_margin_info = {"margin": 0.45, "is_default": True}

    def _get_margin_info(cat: str) -> Dict:
        """Resolve margin info dict for a category, falling back to Default then hardcoded."""
        return (
            category_margins.get(cat)
            or category_margins.get("Default")
            or _fallback_margin_info
        )

    category_perf = []
    total_profit = 0.0
    if not sales.empty and "Category" in sales.columns:
        for cat_name, group in sales.groupby("Category"):
            cat_str = str(cat_name)
            rev = float(group["Sales"].sum())
            orders = len(group)
            m_info = _get_margin_info(cat_str)
            margin = m_info["margin"]
            cat_profit = float(round(rev * margin, 2))
            total_profit += cat_profit
            category_perf.append({
                "category": cat_str,
                "revenue": round(rev, 2),
                "orders": orders,
                "profit": cat_profit,
                "margin_used": margin,
                "is_default": m_info.get("is_default", True),
            })
        category_perf.sort(key=lambda x: x["revenue"], reverse=True)

    # 8. Batch Performance & Missing Capacity Flagging
    batch_perf = []
    if not sales.empty and "Batch" in sales.columns:
        batches_map = {}
        if batches_df is not None and not batches_df.empty and "Batch" in batches_df.columns:
            for _, b_row in batches_df.iterrows():
                b_name = str(b_row["Batch"])
                b_cap = b_row.get("Capacity") if "Capacity" in batches_df.columns else None
                b_profit = b_row.get("Profit") if "Profit" in batches_df.columns else None
                batches_map[b_name] = {"capacity": b_cap, "profit": b_profit}

        for b_name, group in sales.groupby("Batch"):
            b_str = str(b_name)
            b_rev = float(group["Sales"].sum())
            b_orders = len(group)
            
            # refunds for this batch
            b_refunds = refunds[refunds["Batch"] == b_str] if (not refunds.empty and "Batch" in refunds.columns) else pd.DataFrame()
            b_refund_amt = float(b_refunds["RefundAmount"].sum()) if not b_refunds.empty else 0.0
            net_admissions = b_orders - len(b_refunds)

            batch_info = batches_map.get(b_str, {})
            cap_val = batch_info.get("capacity")

            capacity_missing = (cap_val is None or pd.isna(cap_val))
            if capacity_missing:
                capacity = None
                fill_percent = None
            else:
                try:
                    capacity = int(cap_val)
                    fill_percent = float((net_admissions / capacity) * 100.0) if capacity > 0 else 0.0
                except (ValueError, TypeError):
                    capacity = None
                    fill_percent = None
                    capacity_missing = True

            cat_str = str(group["Category"].iloc[0]) if "Category" in group.columns else "Default"
            b_m_info = _get_margin_info(cat_str)
            b_margin = b_m_info["margin"]
            b_profit = float(batch_info.get("profit")) if (batch_info.get("profit") is not None and not pd.isna(batch_info.get("profit"))) else float(round((b_rev - b_refund_amt) * b_margin, 2))

            batch_perf.append({
                "batch": b_str,
                "revenue": round(b_rev, 2),
                "admissions": net_admissions,
                "capacity": capacity,
                "fill_percent": round(fill_percent, 2) if fill_percent is not None else None,
                "capacity_missing": capacity_missing,
                "profit": b_profit,
                "refund_amount": round(b_refund_amt, 2)
            })
        batch_perf.sort(key=lambda x: x["revenue"], reverse=True)

    # 9. Teacher Performance
    teacher_perf = []
    if not sales.empty and "Teacher" in sales.columns:
        for t_name, group in sales.groupby("Teacher"):
            t_rev = float(group["Sales"].sum())
            t_adm = len(group)
            teacher_perf.append({
                "teacher": str(t_name),
                "revenue": round(t_rev, 2),
                "admissions": t_adm
            })
        teacher_perf.sort(key=lambda x: x["revenue"], reverse=True)

    # 10. State Performance
    state_perf = []
    if not sales.empty and "State" in sales.columns:
        for st_name, group in sales.groupby("State"):
            st_rev = float(group["Sales"].sum())
            state_perf.append({
                "state": str(st_name),
                "revenue": round(st_rev, 2)
            })
        state_perf.sort(key=lambda x: x["revenue"], reverse=True)

    loss = refund_amount

    return {
        "gross_revenue": round(gross_revenue, 2),
        "net_revenue": round(net_revenue, 2),
        "refund_amount": round(refund_amount, 2),
        "refund_percent": round(refund_percent, 2),
        "orders": total_orders,
        "average_selling_price": round(average_selling_price, 2),
        "today_sales": round(today_sales, 2),
        "yesterday_sales": round(yesterday_sales, 2),
        "daily_run_rate": round(daily_run_rate, 2),
        "wow_growth": round(wow_growth, 2),
        "mom_growth": round(mom_growth, 2),
        "days_compared": days_compared,
        "target_data_missing": target_data_missing,
        "total_target": round(total_target, 2) if total_target is not None else None,
        "target_achieved_percent": round(target_achieved_percent, 2) if target_achieved_percent is not None else None,
        "target_remaining": round(target_remaining, 2) if target_remaining is not None else None,
        "required_drr": round(required_drr, 2) if required_drr is not None else None,
        "expected_month_revenue": round(expected_month_revenue, 2) if expected_month_revenue is not None else None,
        "forecast_target_achievement": round(forecast_target_achievement, 2) if forecast_target_achievement is not None else None,
        "profit": round(total_profit, 2),
        "loss": round(loss, 2),
        "category_performance": category_perf,
        "batch_performance": batch_perf,
        "teacher_performance": teacher_perf,
        "state_performance": state_perf
    }
