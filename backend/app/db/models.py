"""
app/db/models.py
─────────────────
Database interaction helpers using the Supabase Python SDK (supabase-py).
No ORM — we talk directly to Supabase so that RLS policies apply naturally to
reads and the service-role client is used for writes (after app-layer auth checks).

All public functions accept/return plain Python dicts or typed dataclasses so that
callers don't need to import supabase-py directly.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional


# ── Internal helpers ─────────────────────────────────────────────────────────

def _admin():
    """Return the service-role Supabase client (bypasses RLS — use only after auth check)."""
    from app.core.supabase_client import supabase_admin
    if supabase_admin is None:
        raise RuntimeError(
            "Supabase admin client is not initialised. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env."
        )
    return supabase_admin


# ── Dataset CRUD ─────────────────────────────────────────────────────────────

def create_dataset(
    org_id: str,
    uploaded_by: str,
    filename: str,
    status: str = "pending",
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a datasets row and return the created record."""
    payload = {
        "id": str(uuid.uuid4()),
        "org_id": org_id,
        "uploaded_by": uploaded_by,
        "filename": filename,
        "status": status,
        "storage_path": storage_path,
    }
    result = _admin().table("datasets").insert(payload).execute()
    return result.data[0]


def update_dataset(dataset_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Patch a datasets row by id and return the updated record."""
    result = _admin().table("datasets").update(updates).eq("id", dataset_id).execute()
    return result.data[0]


def get_dataset(dataset_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single dataset row by id. Returns None if not found."""
    result = _admin().table("datasets").select("*").eq("id", dataset_id).execute()
    return result.data[0] if result.data else None


# ── KPI Snapshot CRUD ────────────────────────────────────────────────────────

def create_kpi_snapshot(
    dataset_id: str,
    kpi_json: Dict[str, Any],
    category_margins_used: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Insert a kpi_snapshots row and return the created record."""
    payload = {
        "id": str(uuid.uuid4()),
        "dataset_id": dataset_id,
        "kpi_json": kpi_json,
        "category_margins_used": category_margins_used or {},
    }
    result = _admin().table("kpi_snapshots").insert(payload).execute()
    return result.data[0]


def get_kpi_snapshot_by_dataset(dataset_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recent kpi_snapshot for a dataset_id."""
    result = (
        _admin()
        .table("kpi_snapshots")
        .select("*")
        .eq("dataset_id", dataset_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


# ── Audit Log ────────────────────────────────────────────────────────────────

def create_audit_entry(
    org_id: str,
    user_id: str,
    action: str,
    details: Dict[str, Any],
    dataset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert an audit_log row and return it."""
    payload = {
        "id": str(uuid.uuid4()),
        "org_id": org_id,
        "user_id": user_id,
        "dataset_id": dataset_id,
        "action": action,
        "details": details,
    }
    result = _admin().table("audit_log").insert(payload).execute()
    return result.data[0]


def get_audit_entries_for_dataset(dataset_id: str) -> List[Dict[str, Any]]:
    """Return all audit_log rows for a given dataset_id, newest first."""
    result = (
        _admin()
        .table("audit_log")
        .select("*")
        .eq("dataset_id", dataset_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


# ── Supabase Storage ─────────────────────────────────────────────────────────

def upload_to_storage(
    bucket: str,
    path: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload file_bytes to Supabase Storage at bucket/path.
    Returns the storage path on success.
    """
    _admin().storage.from_(bucket).upload(
        path=path,
        file=file_bytes,
        file_options={"content-type": content_type},
    )
    return path


# ── Insight Cache ─────────────────────────────────────────────────────────────

def get_cached_insights(dataset_id: str, scope: str, kpi_hash: str) -> Optional[Dict[str, Any]]:
    """Fetch cached insights for a (dataset_id, scope, kpi_hash) key."""
    result = (
        _admin()
        .table("insight_cache")
        .select("*")
        .eq("dataset_id", dataset_id)
        .eq("scope", scope)
        .eq("kpi_hash", kpi_hash)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def create_insight_cache_entry(
    dataset_id: str,
    scope: str,
    kpi_hash: str,
    insights_json: List[Dict[str, Any]],
    provider_used: str,
) -> Dict[str, Any]:
    """Store generated insights in cache."""
    payload = {
        "id": str(uuid.uuid4()),
        "dataset_id": dataset_id,
        "scope": scope,
        "kpi_hash": kpi_hash,
        "insights_json": insights_json,
        "provider_used": provider_used,
    }
    result = _admin().table("insight_cache").insert(payload).execute()
    return result.data[0]


# ── Usage Log (Rate Limiting) ──────────────────────────────────────────────────

def record_usage(user_id: str, action: str) -> Dict[str, Any]:
    """Record an action in usage_log."""
    payload = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "action": action,
    }
    result = _admin().table("usage_log").insert(payload).execute()
    return result.data[0]


def get_user_usage_count_today(user_id: str, action: str) -> int:
    """Return count of actions by user_id since start of today (UTC)."""
    from datetime import datetime, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    result = (
        _admin()
        .table("usage_log")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("action", action)
        .gte("created_at", today_start)
        .execute()
    )
    return result.count if result.count is not None else len(result.data or [])

