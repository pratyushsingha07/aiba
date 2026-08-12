"""
app/services/grounding_validator.py
───────────────────────────────────
Grounding Validator for AI Insights & Answers.

Verifies that:
1. No referenced field in kpi_data is null/None or flagged as scoped out.
2. Every number / percentage mentioned in the text matches an actual value in kpi_data
   within ±0.5% rounding tolerance.

If validation fails:
- Marks insight as verified=False with unverified_reason ("referenced_null_field" | "number_mismatch").
- Logs failure to audit_log table with action="insight_grounding_failed".
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from app.services.insight_engine import Insight

logger = logging.getLogger(__name__)

# Regex to extract numbers and percentages e.g. 1500, 50.5%, $1,000, ₹60,000
NUMBER_REGEX = re.compile(r'(?:[₹$€£]\s*)?([+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*%?')


def _flatten_kpi_values(data: Any, prefix: str = "") -> Dict[str, Any]:
    """Recursively flatten dictionary into dotted-path keys -> values."""
    flat = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            flat.update(_flatten_kpi_values(v, key))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            key = f"{prefix}.{idx}"
            flat.update(_flatten_kpi_values(item, key))
    else:
        flat[prefix] = data
    return flat


def _parse_extracted_number(num_str: str) -> Optional[float]:
    """Clean string number (remove commas, currency symbols) and convert to float."""
    try:
        clean = num_str.replace(',', '').replace('$', '').replace('₹', '').replace('%', '').strip()
        return float(clean)
    except (ValueError, TypeError):
        return None


def _get_value_at_path(data: Dict[str, Any], path: str) -> Any:
    """Retrieve value at dotted path e.g. 'category_performance.0.revenue'."""
    parts = path.split('.')
    curr = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
            curr = curr[int(part)]
        else:
            return None
    return curr


def _check_number_match(target_val: float, kpi_values: List[float], tolerance: float = 0.005) -> bool:
    """Check if target_val matches any value in kpi_values within relative tolerance (±0.5%)."""
    for v in kpi_values:
        if v is None:
            continue
        # Check absolute difference or relative difference
        diff = abs(target_val - v)
        if diff <= 0.01:  # small absolute match
            return True
        if abs(v) > 0 and (diff / abs(v)) <= tolerance:
            return True
    return False


def validate_single_insight(insight: Insight, kpi_data: Dict[str, Any]) -> Insight:
    """
    Validate a single Insight against kpi_data.
    Returns the updated Insight with verified=True/False and unverified_reason set.
    """
    flat_kpis = _flatten_kpi_values(kpi_data)

    # ── Check 1: Referenced Null Fields ──────────────────────────────────────
    # Check if any path cited in supporting_kpi_ids or matching null keys in kpi_data is referenced
    for path in insight.supporting_kpi_ids:
        val = _get_value_at_path(kpi_data, path)
        if val is None:
            insight.verified = False
            insight.unverified_reason = "referenced_null_field"
            return insight

    # Check text for mentions of null fields or scoped-out flags
    text_to_check = f"{insight.insight} {insight.recommendation}".lower()
    null_keys = [k for k, v in flat_kpis.items() if v is None]
    for nk in null_keys:
        key_short_name = nk.split('.')[-1].lower()
        if key_short_name in ["total_target", "mom_growth", "wow_growth", "expected_month_revenue"] and key_short_name in text_to_check:
            # Check if text claims a value for this null field
            matches = NUMBER_REGEX.findall(text_to_check)
            if matches:
                insight.verified = False
                insight.unverified_reason = "referenced_null_field"
                return insight

    # ── Check 2: Number Mismatch ─────────────────────────────────────────────
    # Extract all numbers from insight and recommendation text
    full_text = f"{insight.insight} {insight.recommendation}"
    extracted_matches = NUMBER_REGEX.findall(full_text)
    extracted_numbers = []
    for m in extracted_matches:
        num = _parse_extracted_number(m)
        if num is not None and num not in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]: # Exclude small integers used as bullet counts
            extracted_numbers.append(num)

    if not extracted_numbers:
        insight.verified = True
        insight.unverified_reason = None
        return insight

    # Collect numeric values present in kpi_data
    all_kpi_numbers = []
    for k, v in flat_kpis.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            all_kpi_numbers.append(float(v))

    for num in extracted_numbers:
        if not _check_number_match(num, all_kpi_numbers, tolerance=0.005):
            insight.verified = False
            insight.unverified_reason = "number_mismatch"
            return insight

    insight.verified = True
    insight.unverified_reason = None
    return insight


def validate_grounding(
    insights: List[Insight],
    kpi_data: Dict[str, Any],
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
) -> List[Insight]:
    """
    Validates grounding for a list of insights against kpi_data.
    Logs audit entry for any insight that fails verification.
    """
    validated_insights = []
    for insight in insights:
        v_insight = validate_single_insight(insight, kpi_data)
        if not v_insight.verified:
            logger.warning(
                f"Grounding failure detected: reason={v_insight.unverified_reason}, "
                f"insight='{v_insight.insight}'"
            )
            # Log to audit_log if context provided
            if org_id and user_id:
                try:
                    from app.db import models as db
                    db.create_audit_entry(
                        org_id=org_id,
                        user_id=user_id,
                        dataset_id=dataset_id,
                        action="insight_grounding_failed",
                        details={
                            "reason": v_insight.unverified_reason,
                            "insight_text": v_insight.insight,
                            "recommendation": v_insight.recommendation,
                            "supporting_kpi_ids": v_insight.supporting_kpi_ids,
                        },
                    )
                except Exception as exc:
                    logger.error(f"Failed to log grounding audit entry: {exc}")
        validated_insights.append(v_insight)
    return validated_insights
