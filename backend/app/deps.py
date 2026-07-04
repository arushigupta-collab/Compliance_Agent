"""Adapter selection by env flags. The only place that branches on DATA_SOURCE/STORAGE."""
from __future__ import annotations

from functools import lru_cache

from app.config import settings


@lru_cache
def get_repository():
    if settings.data_source == "supabase":
        from app.repo.supabase_repo import SupabaseRepository
        return SupabaseRepository()
    from app.repo.local_repo import LocalRepository
    return LocalRepository()


@lru_cache
def get_storage():
    if settings.storage == "supabase":
        from app.storage.supabase_storage import SupabaseStorage
        return SupabaseStorage()
    from app.storage.local_storage import LocalStorage
    return LocalStorage()
