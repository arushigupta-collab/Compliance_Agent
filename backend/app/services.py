"""Application services: assemble domain aggregates from the repository."""
from __future__ import annotations

from app.deps import get_repository
from app.domain.models import ChecklistRow, CompanyProfile, PassportVerification, Person
from app.rules.checklist import required_documents
from app.vision import face, passport


def ensure_kyc(repo, company_id: str, person: Person) -> PassportVerification:
    """Create a deterministic KYC verification from the person's document fields
    (no images) if one doesn't exist. Used by headless runs (e.g. the oracle) so
    DVO — which now strictly depends on KYC — has an identity verdict to gate on."""
    existing = {pv.person_id: pv for pv in repo.get_passport_verifications(company_id)}
    if person.id in existing:
        return existing[person.id]
    checks = passport.field_checks(expiry=person.passport_expiry, poa_date=person.poa_date,
                                   doc_name=None, person_name=person.name, mrz_valid=True)
    face_res = face.fallback_match(checks["passed"])
    all_checks = {**checks, **{f"face_{k}": v for k, v in face_res.items()}}
    overall = "verified" if (checks["passed"] and face_res.get("passed")) else "flagged"
    pv = PassportVerification(
        company_id=company_id, person_id=person.id, person_name=person.name,
        mrz={}, extracted={"name": person.name, "expiry": str(person.passport_expiry),
                           "poa_date": str(person.poa_date)},
        face_match_score=face_res.get("face_match_score"), checks=all_checks, overall=overall)
    pv.id = repo.save_passport_verification(pv)
    return pv


def build_profile(sr: str) -> CompanyProfile | None:
    from app.config import settings

    repo = get_repository()
    company = repo.get_company(sr)
    if not company:
        return None
    people = repo.get_people(company.id)
    statuses = {d.doc_key: d for d in repo.get_document_status(company.id)}

    supabase_mode = settings.data_source == "supabase"
    if supabase_mode:
        from app.supabase_map import requirements_supabase
        domain = (company.attributes or {}).get("domain", "")
        rdt, ft = repo.requirements_meta(domain)
        reqs = requirements_supabase(domain, rdt, ft, bool((company.attributes or {}).get("high_risk_activity")))
    else:
        reqs = required_documents(company)

    checklist: list[ChecklistRow] = []
    for r in reqs:
        st = statuses.get(r.doc_key)
        checklist.append(ChecklistRow(
            doc_key=r.doc_key, label=r.label, source=r.source, required=r.required,
            status=st.status if st else "missing",
            filename=st.filename if st else None,
            extracted_fields=st.extracted_fields if st else {},
        ))

    pvs = repo.get_passport_verifications(company.id)
    # A person is "cleared to run" once their passport has been CHECKED (any
    # verdict). A flagged passport still runs — DVO formally raises the flag,
    # which is exactly the Fireblocks/Jupiter demo path.
    checked_person_ids = {pv.person_id for pv in pvs}

    blockers: list[str] = []
    # In Supabase mode documents-present is informational (drafts may be incomplete);
    # only KYC gates the run. In local mode, missing required docs also block.
    if not supabase_mode:
        missing = [c.doc_key for c in checklist if c.required and c.status == "missing"]
        if missing:
            blockers.append(f"{len(missing)} required document(s) missing: {', '.join(missing)}")
    unchecked = [p.name for p in people if p.id not in checked_person_ids]
    if unchecked:
        blockers.append(f"Passport not checked for: {', '.join(unchecked)}")

    return CompanyProfile(
        company=company, people=people, checklist=checklist,
        passport_verifications=pvs, can_run=not blockers, run_blockers=blockers,
    )
