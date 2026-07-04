"""StorageAdapter interface. Selected by STORAGE=local|supabase."""
from __future__ import annotations

from typing import Protocol

# Logical buckets/dirs.
RAW_DOCUMENTS = "raw-documents"
PASSPORT_IMAGES = "passport-images"
SELFIES = "selfies"
GENERATED_OUTPUTS = "generated-outputs"


class StorageAdapter(Protocol):
    def put(self, bucket: str, key: str, data: bytes) -> str:
        """Store bytes, return a storage_path handle."""
        ...

    def get(self, path: str) -> bytes:
        ...

    def url(self, path: str) -> str:
        ...
