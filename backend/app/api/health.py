"""Schema health check — validate live DB against expected views/fields.

Surfaces drift as a UI banner instead of a crash (spec §7.8).
"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import session_scope

router = APIRouter()

# Expected view -> required columns (the contract the app relies on).
EXPECTED: dict[str, set[str]] = {
    "v_companies": {"id", "sr", "name", "archetype", "company_type", "activity", "activity_class",
                    "risk_tier", "jurisdiction", "package", "visa_quota", "premium", "token_issuing",
                    "preapproval_status", "status", "attributes"},
    "v_company_people": {"id", "company_id", "name", "role", "nationality", "dob", "pob",
                         "passport_no", "passport_issue", "passport_expiry", "issuing_authority",
                         "address", "poa_source", "poa_date", "ubo_pct", "is_ubo", "is_signatory", "attributes"},
    "v_document_status": {"company_id", "doc_key", "source", "status", "filename", "extracted_fields"},
    "v_run_summary": {"run_id", "company_id", "status", "started_at", "finished_at", "stages"},
}


@router.get("/health/schema")
def schema_health() -> dict:
    with session_scope() as s:
        rows = s.execute(text("""
            select table_name, column_name
            from information_schema.columns
            where table_schema = 'public' and table_name = any(:views)
        """), {"views": list(EXPECTED.keys())}).all()

    present: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        present.setdefault(table_name, set()).add(column_name)

    missing_views = [v for v in EXPECTED if v not in present]
    missing_fields: list[str] = []
    for view, cols in EXPECTED.items():
        for col in cols - present.get(view, set()):
            missing_fields.append(f"{view}.{col}")

    return {"ok": not missing_views and not missing_fields,
            "missing_views": sorted(missing_views),
            "missing_fields": sorted(missing_fields)}
