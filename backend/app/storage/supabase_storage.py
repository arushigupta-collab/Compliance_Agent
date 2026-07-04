"""Supabase Storage adapter — reads files from the customer-portal bucket.

Runtime uploads (KYC passport/selfie) stay on local disk; this adapter is used to
read/serve existing portal documents from the `application-files` bucket.
"""
from __future__ import annotations

from app import supabase_client as sb


class SupabaseStorage:
    def get(self, path: str) -> bytes:
        data = sb.download(path)
        if data is None:
            raise FileNotFoundError(f"Supabase object not found: {path}")
        return data

    def url(self, path: str) -> str:
        return sb.signed_url(path) or ""

    def put(self, bucket: str, key: str, data: bytes) -> str:  # pragma: no cover
        # Runtime writes go to local storage in this deployment; portal DB is read-only.
        raise NotImplementedError("SupabaseStorage is read-only; use LocalStorage for uploads (STORAGE=local).")
