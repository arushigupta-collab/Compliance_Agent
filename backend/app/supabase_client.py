"""Thin Supabase client over PostgREST + Storage (httpx, service-role key).

Read-only against the customer-portal project. No supabase-py dependency.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config import settings


def configured() -> bool:
    return bool(settings.sb_url and settings.sb_service_key)


def _headers() -> dict[str, str]:
    key = settings.sb_service_key
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def select(table: str, *, filters: Optional[dict[str, str]] = None, select_cols: str = "*",
           order: Optional[str] = None, limit: Optional[int] = None) -> list[dict[str, Any]]:
    """GET /rest/v1/<table> with PostgREST filters, e.g. filters={'application_id': 'eq.<uuid>'}."""
    params: dict[str, str] = {"select": select_cols}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    if limit:
        params["limit"] = str(limit)
    url = f"{settings.sb_url}/rest/v1/{table}"
    resp = httpx.get(url, headers=_headers(), params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def get_one(table: str, row_id: str, *, id_col: str = "id") -> Optional[dict[str, Any]]:
    rows = select(table, filters={id_col: f"eq.{row_id}"}, limit=1)
    return rows[0] if rows else None


def signed_url(path: str, *, expires_in: int = 3600) -> Optional[str]:
    """Create a signed URL for a file in the storage bucket."""
    if not path:
        return None
    bucket = settings.supabase_bucket
    url = f"{settings.sb_url}/storage/v1/object/sign/{bucket}/{path}"
    try:
        resp = httpx.post(url, headers=_headers(), json={"expiresIn": expires_in}, timeout=30.0)
        resp.raise_for_status()
        signed = resp.json().get("signedURL") or resp.json().get("signedUrl")
        return f"{settings.sb_url}/storage/v1{signed}" if signed else None
    except Exception:
        return None


def download(path: str) -> Optional[bytes]:
    """Download raw bytes of a file from the bucket (service-role)."""
    if not path:
        return None
    bucket = settings.supabase_bucket
    url = f"{settings.sb_url}/storage/v1/object/{bucket}/{path}"
    try:
        resp = httpx.get(url, headers=_headers(), timeout=60.0)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None
