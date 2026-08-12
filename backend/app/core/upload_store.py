"""
app/core/upload_store.py
─────────────────────────
In-memory store for pending (unconfirmed) uploads.

Each entry lives until either:
  - The user calls POST /confirm-mapping (evicted on success or blocking error)
  - upload_ttl_seconds elapses without confirmation (lazy expiry checked on every access)

V1 LIMITATION: This store is in-process only — it does NOT survive server restarts
and does NOT work in a multi-process/multi-worker deployment. For production scale,
replace with a Redis-backed store or a `pending_uploads` Postgres table.
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class PendingUpload:
    upload_id: str
    filename: str
    file_bytes: bytes
    # Detected DataFrames keyed by sheet type: "sales", "refunds", "targets", "batches"
    sheet_dfs: Dict[str, pd.DataFrame]
    # Proposed mapping per sheet type: { sheet_type: { system_field: user_column | None } }
    proposed_mapping: Dict[str, Dict[str, Optional[str]]]
    created_at: float = field(default_factory=time.time)


class UploadStore:
    """Thread-safe-ish in-memory TTL store for pending uploads."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._store: Dict[str, PendingUpload] = {}
        self.ttl_seconds = ttl_seconds

    def put(self, pending: PendingUpload) -> str:
        self._evict_expired()
        self._store[pending.upload_id] = pending
        return pending.upload_id

    def get(self, upload_id: str) -> Optional[PendingUpload]:
        self._evict_expired()
        return self._store.get(upload_id)

    def evict(self, upload_id: str) -> None:
        self._store.pop(upload_id, None)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v.created_at > self.ttl_seconds]
        for k in expired:
            del self._store[k]


def create_upload_id() -> str:
    return str(uuid.uuid4())


# Module-level singleton — imported everywhere as `pending_store`
from app.core.config import get_settings as _get_settings

def _make_store() -> UploadStore:
    try:
        return UploadStore(ttl_seconds=_get_settings().upload_ttl_seconds)
    except Exception:
        return UploadStore()

pending_store = _make_store()
