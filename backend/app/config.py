"""Environment configuration. Single source of truth for env flags."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from the repo root (two levels up from this file: app/ -> backend/ -> repo/)
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_REPO_ROOT / ".env"), extra="ignore")

    data_source: str = "local"          # local | supabase
    storage: str = "local"              # local | supabase
    database_url: str = "postgresql://rak:rak@localhost:5432/rak"
    review_date: date = date(2026, 1, 15)
    face_match_threshold: float = 0.363
    auto_escalate: bool = True
    face_source: str = "runtime"        # runtime | seeded

    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet"

    dataset_root: str = str(_REPO_ROOT / "files" / "RAK_Compliance_Demo_Documents")
    dataset_index: str = str(_REPO_ROOT / "files" / "_INDEX.csv")
    storage_root: str = str(_REPO_ROOT / "storage")

    # Supabase — accepts either our names or the NEXT_PUBLIC_* / SERVICE_ROLE names.
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_service_key: str = ""            # legacy alias
    supabase_bucket: str = "application-files"
    supabase_bucket_prefix: str = "rak"

    # NEXT_PUBLIC_* aliases (populated from .env by pydantic-settings via env names below)
    next_public_supabase_url: str = ""
    next_public_supabase_anon_key: str = ""

    @property
    def sb_url(self) -> str:
        return (self.supabase_url or self.next_public_supabase_url).rstrip("/")

    @property
    def sb_service_key(self) -> str:
        return self.supabase_service_role_key or self.supabase_service_key

    @property
    def sb_anon_key(self) -> str:
        return self.supabase_anon_key or self.next_public_supabase_anon_key

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
