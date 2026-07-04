"""Translate view rows -> domain models, honoring mapping.yaml.

Schema-tolerant: selects known fields with typed defaults via the remap table,
ignores unknown columns. This is the only place that knows about column names.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

from app.domain.models import Company, DocumentStatus, Person

_MAPPING_PATH = Path(__file__).with_name("mapping.yaml")


@lru_cache
def _mapping() -> dict[str, dict[str, str]]:
    with open(_MAPPING_PATH) as f:
        return yaml.safe_load(f) or {}


def _pick(row: Mapping[str, Any], section: str) -> dict[str, Any]:
    """Pull domain-field -> value using the remap table; missing cols -> None."""
    remap = _mapping().get(section, {})
    out: dict[str, Any] = {}
    for domain_field, source_col in remap.items():
        out[domain_field] = row.get(source_col)
    return out


def _to_str(v: Any) -> Any:
    return str(v) if v is not None else None


def company_from_row(row: Mapping[str, Any]) -> Company:
    d = _pick(row, "company")
    d["id"] = _to_str(d.get("id"))
    d["attributes"] = d.get("attributes") or {}
    d["visa_quota"] = d.get("visa_quota") or 1
    d["premium"] = bool(d.get("premium"))
    d["token_issuing"] = bool(d.get("token_issuing"))
    return Company(**d)


def person_from_row(row: Mapping[str, Any]) -> Person:
    d = _pick(row, "person")
    d["id"] = _to_str(d.get("id"))
    d["company_id"] = _to_str(d.get("company_id"))
    d["attributes"] = d.get("attributes") or {}
    d["is_ubo"] = bool(d.get("is_ubo"))
    d["is_signatory"] = bool(d.get("is_signatory"))
    return Person(**d)


def document_status_from_row(row: Mapping[str, Any]) -> DocumentStatus:
    d = _pick(row, "document_status")
    d["company_id"] = _to_str(d.get("company_id"))
    d["extracted_fields"] = d.get("extracted_fields") or {}
    d["status"] = d.get("status") or "missing"
    return DocumentStatus(**d)
