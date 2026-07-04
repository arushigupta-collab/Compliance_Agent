"""Local filesystem StorageAdapter: ./storage/<bucket>/<company>/<key>."""
from __future__ import annotations

from pathlib import Path

from app.config import settings


class LocalStorage:
    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.storage_root)

    def _abs(self, bucket: str, key: str) -> Path:
        return self.root / bucket / key

    def put(self, bucket: str, key: str, data: bytes) -> str:
        dest = self._abs(bucket, key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        # storage_path is relative to the storage root so it survives a move.
        return str(Path(bucket) / key)

    def get(self, path: str) -> bytes:
        return (self.root / path).read_bytes()

    def url(self, path: str) -> str:
        # Local: served by the API's /files route.
        return f"/api/v1/files/{path}"
