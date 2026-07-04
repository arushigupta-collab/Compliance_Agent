"""Required-document derivation per spec §7.4.

The generated baseline plus risk/premium triggers, and the archetype-specific
uploaded set. Labels mirror the real dataset (_INDEX.csv) doc_key scheme.
"""
from __future__ import annotations

from app.domain.models import Company, DocumentRequirement

# ---- Generated baseline (portal system output) ----
_GENERATED_BASE = [
    ("G01", "Application / SR Record"),
    ("G02", "Name Reservation Approval"),
    ("G03", "Payment Confirmation"),
    ("G04", "Shareholder / Director Register"),
    ("G05", "Client Confirmation Letter"),
    ("G06", "Memorandum of Association (MOA)"),        # skipped for DAO
    ("G07", "UBO Declaration"),
    ("G08", "Final Declarations / Signed Application"),
]
_G09 = ("G09", "Source of Wealth Statement")           # high risk
_G10 = ("G10", "Premium Activity Pre-Approval Request")  # premium

# ---- Uploaded sets by archetype (customer-supplied) ----
_UPLOAD_INDIVIDUAL = [
    ("U01", "Passport / ID — Founder"),
    ("U02", "Proof of Address — Founder"),
]
_UPLOAD_CORPORATE = [
    ("U01", "Passport / ID — Signatory"),
    ("U02", "Proof of Address — Signatory"),
    ("U03", "Parent — Certificate of Incorporation"),
    ("U04", "Parent — MoA / AoA"),
    ("U05", "Parent — Certificate of Good Standing"),
    ("U06", "Board Resolution"),
    ("U07", "Power of Attorney"),
    ("U08", "UBO Identity Documents"),
]
_UPLOAD_DAO = [
    ("U01", "Passport / ID — Member 1"),
    ("U02", "Proof of Address — Member 1"),
    ("U03", "Passport / ID — Member 2"),
    ("U04", "Proof of Address — Member 2"),
    ("U05", "DAO Constitution"),
    ("U06", "Memorandum of Association (CLG)"),
    ("U07", "Tokenomics"),
    ("U08", "Whitepaper"),
    ("U09", "Legal Opinion"),
]
_UPLOAD_DAO_TOKEN = ("U10", "Smart-Contract Audit")     # token_issuing DAOs


def is_premium(company: Company) -> bool:
    """Premium guard: match the classification prefix, never a substring
    ("NON-PREMIUM" contains "PREMIUM")."""
    return company.activity_class.strip().upper().startswith("PREMIUM") or company.premium


def is_high_risk(company: Company) -> bool:
    return company.risk_tier.strip().upper() in {"HIGH", "MEDIUM-HIGH"} or is_premium(company)


def required_documents(company: Company) -> list[DocumentRequirement]:
    reqs: list[DocumentRequirement] = []

    # Generated baseline
    for key, label in _GENERATED_BASE:
        if key == "G06" and company.archetype == "dao":
            continue  # DAOs (CLG) have no MOA in the generated pack
        reqs.append(DocumentRequirement(doc_key=key, label=label, source="generated"))
    if is_high_risk(company):
        reqs.append(DocumentRequirement(doc_key=_G09[0], label=_G09[1], source="generated"))
    if is_premium(company):
        reqs.append(DocumentRequirement(doc_key=_G10[0], label=_G10[1], source="generated"))

    # Uploaded set by archetype
    if company.archetype == "individual":
        upload = list(_UPLOAD_INDIVIDUAL)
    elif company.archetype == "corporate":
        upload = list(_UPLOAD_CORPORATE)
    else:  # dao
        upload = list(_UPLOAD_DAO)
        if company.token_issuing:
            upload.append(_UPLOAD_DAO_TOKEN)

    for key, label in upload:
        reqs.append(DocumentRequirement(doc_key=key, label=label, source="uploaded"))

    return reqs


# Generated documents that must carry a signature (checked in DVO).
SIGNABLE_GENERATED = {"G05", "G06", "G07", "G08", "G09"}


# Which documents each pipeline stage reviews. Intersected with the company's
# actual required set, so archetype-specific keys only appear when relevant.
STAGE_DOCS: dict[str, list[str]] = {
    "dvo": ["U01", "U02", "U03", "U04", "G04", "G05", "G08"],
    "compliance": ["G07", "G09", "G10", "U03", "U05", "U06", "U08", "U07", "U09", "U10"],
    "lease": ["G01", "G02", "G03"],
    "rnl": ["G05", "G06", "G08", "G10"],
}


def stage_documents(company: Company, statuses_by_key: dict) -> dict[str, list[dict]]:
    """Resolve each stage's relevant documents to {doc_key, label, source, status, filename}.

    `statuses_by_key` maps doc_key -> DocumentStatus (or None). Only documents the
    company actually requires are included, so the list is archetype-correct.
    """
    reqs = {r.doc_key: r for r in required_documents(company)}
    out: dict[str, list[dict]] = {}
    for stage, keys in STAGE_DOCS.items():
        docs = []
        for k in keys:
            r = reqs.get(k)
            if not r:
                continue
            st = statuses_by_key.get(k)
            docs.append({
                "doc_key": k, "label": r.label, "source": r.source,
                "status": getattr(st, "status", None) or "missing",
                "filename": getattr(st, "filename", None),
            })
        out[stage] = docs
    return out
