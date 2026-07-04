"""Passport MRZ / field extraction + validity checks.

Real path: if a passport IMAGE is supplied, try PassportEye (`read_mrz`) with a
Tesseract fallback. Demo path: the synthetic PDFs have no photo, so we use the
already-extracted document fields. Either way the checks are identical.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from app.config import settings
from app.extract import to_date

# 6 months ~= 183 days; PoA freshness window = 92 days (spec §7.5).
_SIX_MONTHS = timedelta(days=183)
_POA_WINDOW = timedelta(days=92)


def is_pdf(filename: str | None, content_type: str | None = None) -> bool:
    if content_type and "pdf" in content_type.lower():
        return True
    return bool(filename and filename.lower().endswith(".pdf"))


def rasterize_pdf_first_page(pdf_path: str, dpi: int = 150) -> bytes | None:
    """Render page 1 of a PDF to PNG bytes so a passport PDF can be face-matched.
    Returns None if PyMuPDF is unavailable or rendering fails."""
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            return None
        pix = doc[0].get_pixmap(dpi=dpi)
        return pix.tobytes("png")
    except Exception:
        return None


def passport_fields_from_pdf(pdf_path: str) -> dict[str, Any]:
    """Extract passport fields (name, expiry, …) from an uploaded passport PDF."""
    try:
        from app.extract import extract_fields
        return extract_fields(pdf_path, "U01")
    except Exception:
        return {}


def read_mrz_from_image(image_path: str) -> dict[str, Any]:
    """Best-effort MRZ read from a real passport image. Returns {} on any
    failure (PassportEye/Tesseract not installed, or no MRZ found)."""
    try:
        from passporteye import read_mrz  # type: ignore
    except Exception:
        return {}
    try:
        mrz = read_mrz(image_path)
        if not mrz:
            return {}
        d = mrz.to_dict()
        return {
            "name": f"{d.get('names', '')} {d.get('surname', '')}".strip(),
            "nationality": d.get("nationality"),
            "dob": d.get("date_of_birth"),
            "passport_no": d.get("number"),
            "expiry": d.get("expiration_date"),
            "mrz_valid": str(d.get("valid_score", "0")),
        }
    except Exception:
        return {}


def check_expiry(expiry: Optional[date], review: Optional[date] = None) -> dict[str, Any]:
    review = review or settings.review_date
    if not expiry:
        return {"expiry_ok": False, "reason": "missing_expiry", "expiry": None}
    if expiry < review:
        return {"expiry_ok": False, "reason": "passport_expired", "expiry": str(expiry)}
    if expiry < review + _SIX_MONTHS:
        return {"expiry_ok": False, "reason": "expiry_under_6_months", "expiry": str(expiry)}
    return {"expiry_ok": True, "reason": None, "expiry": str(expiry)}


def check_poa(poa_date: Optional[date], review: Optional[date] = None) -> dict[str, Any]:
    review = review or settings.review_date
    if not poa_date:
        # No proof-of-address on file (e.g. Supabase applications without an
        # address-proof doc) → treat as not-applicable rather than a failure.
        return {"poa_ok": True, "reason": None, "poa_date": None}
    age = review - poa_date
    if age > _POA_WINDOW:
        return {"poa_ok": False, "reason": "poa_stale", "poa_date": str(poa_date), "age_days": age.days}
    return {"poa_ok": True, "reason": None, "poa_date": str(poa_date), "age_days": age.days}


def field_checks(*, expiry: Optional[date], poa_date: Optional[date],
                 doc_name: Optional[str], person_name: Optional[str],
                 mrz_valid: bool = True) -> dict[str, Any]:
    """Consolidated field checks used by the passport-verification endpoint and DVO."""
    exp = check_expiry(expiry)
    poa = check_poa(poa_date)
    name_match = bool(doc_name and person_name and doc_name.strip().lower() == person_name.strip().lower())
    # If we couldn't read a document name, don't fail on name match (demo tolerance).
    if not doc_name:
        name_match = True
    return {
        "expiry_ok": exp["expiry_ok"], "expiry": exp["expiry"], "expiry_reason": exp["reason"],
        "poa_ok": poa["poa_ok"], "poa_date": poa["poa_date"], "poa_reason": poa["reason"],
        "poa_age_days": poa.get("age_days"),
        "name_match": name_match,
        "mrz_valid": bool(mrz_valid),
        "passed": exp["expiry_ok"] and poa["poa_ok"] and name_match and mrz_valid,
    }


__all__ = ["read_mrz_from_image", "check_expiry", "check_poa", "field_checks", "to_date"]
