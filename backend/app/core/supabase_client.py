"""
app/core/supabase_client.py
────────────────────────────
Initialises the Supabase Python SDK clients.

Two clients are exposed:
  - `supabase_admin`  — uses the SERVICE_KEY; bypasses RLS; only used server-side for
                        Storage uploads and writing data after we have already enforced
                        app-layer checks. NEVER expose this key or client to the browser.
  - `supabase_anon`   — uses the ANON_KEY; respects RLS; can be used for reads that should
                        be bound by row-level policies.

Both return None-safe objects so that the app starts without a .env file during tests
(mocks replace the actual clients in the test suite).
"""
from __future__ import annotations
from typing import Optional

from app.core.config import get_settings


def _create_admin_client():
    """Create service-role Supabase client. Returns None if credentials are missing."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        return None
    try:
        from supabase import create_client
        return create_client(settings.supabase_url, settings.supabase_service_key)
    except Exception:
        return None


def _create_anon_client():
    """Create anon Supabase client (RLS-aware). Returns None if credentials are missing."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        return None
    try:
        from supabase import create_client
        return create_client(settings.supabase_url, settings.supabase_anon_key)
    except Exception:
        return None


supabase_admin = _create_admin_client()
supabase_anon = _create_anon_client()
