"""
app/core/auth.py
─────────────────
FastAPI dependency: get_current_user()

Validates a Supabase JWT presented in the Authorization: Bearer <token> header.
Extracts user identity from the token's claims WITHOUT a round-trip to Supabase Auth —
we verify the signature locally using JWT_SECRET (the same secret Supabase uses to sign
access tokens: Dashboard → Settings → API → JWT Secret).

Claims used:
  - sub                         → user_id (Supabase Auth UID)
  - app_metadata.org_id         → org_id (set via a Supabase Auth hook or service-role update)
  - app_metadata.role           → role   (admin | business_head | category_manager | analyst)
  - app_metadata.assigned_category → assigned_category (nullable; category_manager only)

HTTP responses:
  401 — token missing, malformed, expired, or bad signature
  403 — token valid but caller does not have access (wrong org, etc.)

The caller is responsible for throwing 403 where org mismatch is detected.
This dependency only validates the token and returns the parsed user.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: str
    org_id: str
    role: str  # admin | business_head | category_manager | analyst
    assigned_category: Optional[str]


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> CurrentUser:
    """
    FastAPI dependency. Validates JWT and returns a CurrentUser.
    Raises 401 if token is missing/invalid, does NOT raise 403 (callers do that).
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},  # Supabase tokens have audience "authenticated"
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Supabase stores custom claims under `app_metadata`
    app_meta = payload.get("app_metadata") or {}

    user_id = payload.get("sub")
    org_id = app_meta.get("org_id")
    role = app_meta.get("role", "analyst")
    assigned_category = app_meta.get("assigned_category")

    if not user_id or not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required claims (sub, app_metadata.org_id)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        user_id=user_id,
        org_id=org_id,
        role=role,
        assigned_category=assigned_category,
    )
