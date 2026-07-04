"""Map the Supabase customer-portal schema (sc.md) → our compliance domain models."""
from __future__ import annotations

from typing import Any, Optional

from app.domain.models import Company, DocumentRequirement, DocumentStatus, Person

# domain → (archetype, risk_tier, premium, token_issuing, preapproval_status)
DOMAIN_MAP: dict[str, tuple[str, str, bool, bool, Optional[str]]] = {
    "standard_fz_llc":    ("individual", "LOW",         False, False, None),
    "subsidiary_foreign": ("corporate",  "MEDIUM",      False, False, None),
    "premium_regulated":  ("corporate",  "HIGH",        True,  False, "pending"),
    "startup_dao":        ("dao",        "MEDIUM-HIGH", True,  False, "pending"),
    "alpha_dao":          ("dao",        "HIGH",        True,  True,  "pending"),
}
_TIER_ORDER = ["LOW", "LOW-MEDIUM", "MEDIUM", "MEDIUM-HIGH", "HIGH"]


def _bump(tier: str) -> str:
    i = _TIER_ORDER.index(tier) if tier in _TIER_ORDER else 2
    return _TIER_ORDER[min(i + 1, len(_TIER_ORDER) - 1)]


def company_from_portal(row: dict[str, Any], package: Optional[dict], status: str = "not_started") -> Company:
    domain = (row.get("domain") or "standard_fz_llc").strip()
    archetype, tier, premium, token, preapproval = DOMAIN_MAP.get(
        domain, ("corporate", "MEDIUM", False, False, None))
    high_risk = bool(row.get("high_risk_activity"))
    if high_risk:
        tier = _bump(tier)
    activity_class = f"PREMIUM ({domain})" if premium else f"Non-premium ({domain})"
    pkg_name = (package or {}).get("name") if package else None
    jurisdiction = "RAK DARe" if archetype == "dao" else "RAK DAO"
    return Company(
        id=str(row["id"]), sr=str(row["id"]),
        name=row.get("company_name") or "(unnamed application)",
        archetype=archetype, company_type=row.get("company_type") or "FZ-LLC",
        activity=row.get("business_description") or domain.replace("_", " "),
        activity_class=activity_class, risk_tier=tier, jurisdiction=jurisdiction,
        package=pkg_name or (row.get("inventory_type") or "Standard package"),
        visa_quota=int(row.get("visa_count") or 0), premium=premium, token_issuing=token,
        preapproval_status=preapproval, status=status,
        attributes={"domain": domain, "high_risk_activity": high_risk,
                    "package_price_cents": (package or {}).get("price_cents"),
                    "contact_name": row.get("contact_name"), "contact_email": row.get("contact_email"),
                    "portal_status": row.get("status")},
    )


def _role(sh: dict[str, Any]) -> str:
    roles = []
    if sh.get("is_director"):
        roles.append("Director")
    if sh.get("is_manager"):
        roles.append("Manager")
    if sh.get("is_authorized_signatory"):
        roles.append("Authorised Signatory")
    if sh.get("shareholder_type") == "corporate":
        roles.append("Corporate Shareholder")
    if not roles:
        roles.append("Shareholder")
    return " / ".join(roles)


def person_from_shareholder(sh: dict[str, Any], poa_date: Optional[str]) -> Person:
    pct = sh.get("ownership_percent")
    return Person(
        id=str(sh["id"]), company_id=str(sh["application_id"]),
        name=sh.get("full_name") or sh.get("corporate_company_name") or "Unknown",
        role=_role(sh), nationality=sh.get("nationality"),
        dob=sh.get("date_of_birth"), pob=None,
        passport_no=sh.get("passport_number"),
        passport_issue=sh.get("passport_issue_date"), passport_expiry=sh.get("passport_expiry_date"),
        issuing_authority=sh.get("passport_issuing_country"),
        address=sh.get("residential_address"), poa_source="address_proof", poa_date=poa_date,
        ubo_pct=f"{pct}%" if pct is not None else None, is_ubo=bool(pct and float(pct) > 0),
        is_signatory=bool(sh.get("is_authorized_signatory")),
        attributes={"is_pep": bool(sh.get("is_pep")), "is_us_person": bool(sh.get("is_us_person")),
                    "shareholder_type": sh.get("shareholder_type"),
                    "source_of_wealth": sh.get("source_of_wealth")},
    )


def doc_status_from_document(doc: dict[str, Any]) -> DocumentStatus:
    """A Supabase `documents` row → DocumentStatus (keyed by type_key)."""
    return DocumentStatus(
        company_id=str(doc["application_id"]), doc_key=doc.get("type_key") or "doc",
        source="generated" if doc.get("kind") == "signed_form" else "uploaded",
        status="extracted", filename=doc.get("file_name"),
        extracted_fields={"kind": doc.get("kind"), "storage_path": doc.get("storage_path"),
                          "mime_type": doc.get("mime_type")},
    )


_STAGE_BY_TYPE = {  # coarse category → pipeline stage for the "documents reviewed" panel
    "passport": "dvo", "address_proof": "dvo", "id_proof": "dvo",
    "source_of_wealth": "compliance", "ubo": "compliance", "bank_reference": "compliance",
    "board_resolution": "compliance", "certificate_of_incorporation": "compliance",
}


def stage_documents_supabase(doc_statuses: list) -> dict[str, list[dict]]:
    """Group actual Supabase documents into pipeline stages for the per-stage panel."""
    out: dict[str, list[dict]] = {"dvo": [], "compliance": [], "lease": [], "rnl": []}
    for d in doc_statuses:
        key = (d.doc_key or "").lower()
        if d.source == "generated":
            stage = "rnl"                       # signed forms surface at Registry & Licensing
        elif "payment" in key or "package" in key or "invoice" in key:
            stage = "lease"
        else:
            stage = _STAGE_BY_TYPE.get(key, "compliance")
        out[stage].append({"doc_key": d.doc_key, "label": d.filename or d.doc_key,
                           "source": d.source, "status": d.status, "filename": d.filename})
    return out


def requirements_supabase(domain: str, req_doc_types: list[dict], form_templates: list[dict],
                          high_risk: bool) -> list[DocumentRequirement]:
    """Supabase-native checklist: signed forms (portal-generated) + required doc types
    and per-person passport/address-proof (customer-uploaded)."""
    def _applies(row: dict) -> bool:
        ad = row.get("applicable_domains") or []
        return (not ad) or (domain in ad)

    reqs: list[DocumentRequirement] = []
    for ft in sorted(form_templates, key=lambda r: r.get("sort_order", 0)):
        if _applies(ft):
            reqs.append(DocumentRequirement(doc_key=ft["key"], label=ft.get("title") or ft["key"],
                                            source="generated", required=True))
    # Per-person identity docs (shareholder kind).
    reqs.append(DocumentRequirement(doc_key="passport", label="Passport / ID", source="uploaded", required=True))
    reqs.append(DocumentRequirement(doc_key="address_proof", label="Proof of Address", source="uploaded", required=True))
    for rd in sorted(req_doc_types, key=lambda r: r.get("sort_order", 0)):
        if _applies(rd) and (rd.get("is_required", True) or (rd.get("key") == "source_of_wealth" and high_risk)):
            reqs.append(DocumentRequirement(doc_key=rd["key"], label=rd.get("label") or rd["key"],
                                            source="uploaded", required=bool(rd.get("is_required", True))))
    return reqs
