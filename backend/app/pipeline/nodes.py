"""Pure per-stage compute + shared persistence.

Each `compute_*` function computes a stage's structured outcome WITHOUT side
effects, LLM calls, or persistence — so the same logic drives both the batch
runner (oracle) and the lazy streaming runner (UI). Persistence and analysis are
applied by the callers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.domain.models import LeaseRecord, License, Person, StageResult
from app.rules.checklist import SIGNABLE_GENERATED, is_premium
from app.rules.risk import escalation_chain, score

ORDER = ["dvo", "compliance", "lease", "rnl"]
STAGE_TITLES = {
    "dvo": "DVO — Document Verification",
    "compliance": "Compliance & Risk",
    "lease": "Lease (CRM)",
    "rnl": "Registry & Licensing",
}

_PACKAGE_FEES = {
    "Flexi-desk (Standard)": "AED 12,500",
    "Standard office": "AED 28,000",
    "DAO package": "AED 22,000",
}
_PREAPPROVAL_ON_FILE = {"approved", "on_file", "complete", "received", "granted"}


@dataclass
class StageOutcome:
    stage: str
    decision: str
    detail: dict                      # structured detail WITHOUT 'analysis'
    terminal: bool = False
    final_status: Optional[str] = None
    company_status: Optional[str] = None
    risk_score: Optional[float] = None
    exceptions: list = field(default_factory=list)
    escalation_chain: list = field(default_factory=list)
    lease_record: Optional[LeaseRecord] = None
    license: Optional[License] = None
    # LLM analysis inputs
    analysis_facts: dict = field(default_factory=dict)
    fallback_reasoning: str = ""
    fallback_insights: list = field(default_factory=list)


def _fee_for(package: str) -> str:
    return _PACKAGE_FEES.get(package.split("/")[0].strip(), "AED 18,000")


def _tier_score(tier: str) -> float:
    return {"LOW": 0.2, "LOW-MEDIUM": 0.35, "MEDIUM": 0.5, "MEDIUM-HIGH": 0.72, "HIGH": 0.9}.get(
        tier.strip().upper(), 0.5)


def _reason_detail(code: str, checks: dict) -> str:
    return {
        "expiry_under_6_months": f"Passport expiry {checks.get('expiry')} is under 6 months from review date.",
        "passport_expired": f"Passport expired on {checks.get('expiry')}.",
        "poa_stale": f"Proof of address dated {checks.get('poa_date')} exceeds the 92-day window.",
        "missing_expiry": "Passport expiry date missing.",
        "missing_poa_date": "Proof-of-address date missing.",
        "face_match_failed": "Face match below threshold.",
        "no_face_detected": "No face detected in passport or selfie.",
        "name_mismatch": "Name on document does not match the registered party.",
    }.get(code, code)


# ---------------------------------------------------------------- DVO
def compute_dvo(company, people: list[Person], pvs: list, docs: list, stage_docs: dict) -> StageOutcome:
    pv_by = {pv.person_id: pv for pv in pvs}
    docmap = {d.doc_key: d for d in docs}
    exceptions: list[dict[str, Any]] = []
    person_results: list[dict[str, Any]] = []

    for p in people:
        pv = pv_by.get(p.id)
        # DVO strictly depends on KYC: a person clears DVO only if their KYC
        # passport-verification exists AND is 'verified'. No verification =>
        # kyc_incomplete; a flagged KYC => DVO carries the KYC failure reasons.
        if pv is None:
            person_results.append({
                "person": p.name, "role": p.role, "passed": False,
                "expiry": None, "expiry_ok": False, "poa_date": None, "poa_ok": False,
                "face_match_score": None, "face_passed": False,
                "kyc": "incomplete", "reasons": ["kyc_incomplete"],
            })
            exceptions.append({"code": "kyc_incomplete", "person": p.name,
                               "detail": f"KYC not completed for {p.name}; DVO cannot verify identity."})
            continue

        c = pv.checks or {}
        kyc_verified = pv.overall == "verified"
        reasons = []
        if not c.get("expiry_ok", True):
            reasons.append(c.get("expiry_reason") or "expiry_check_failed")
        if not c.get("poa_ok", True):
            reasons.append(c.get("poa_reason") or "poa_stale")
        if not c.get("name_match", True):
            reasons.append("name_mismatch")
        if not c.get("face_passed", True):
            reasons.append(c.get("face_reason") or "face_match_failed")
        if not kyc_verified and not reasons:
            reasons.append("kyc_flagged")

        person_results.append({
            "person": p.name, "role": p.role, "passed": kyc_verified,
            "expiry": c.get("expiry"), "expiry_ok": c.get("expiry_ok"),
            "poa_date": c.get("poa_date"), "poa_ok": c.get("poa_ok"),
            "face_match_score": pv.face_match_score, "face_passed": c.get("face_passed"),
            "kyc": pv.overall, "reasons": reasons,
        })
        if not kyc_verified:
            for r in reasons:
                exceptions.append({"code": r, "person": p.name, "detail": _reason_detail(r, c)})

    for key in sorted(SIGNABLE_GENERATED):
        d = docmap.get(key)
        if d and d.status == "extracted" and d.extracted_fields.get("_has_signature") is False:
            exceptions.append({"code": "missing_signature", "doc_key": key,
                               "detail": f"{key} present but no signature detected"})

    passed = len(exceptions) == 0
    decision = "passed" if passed else "flagged"
    detail = {"person_results": person_results, "documents": stage_docs.get("dvo", [])}
    return StageOutcome(
        stage="dvo", decision=decision, detail=detail,
        terminal=not passed, final_status="flagged" if not passed else None,
        company_status="flagged" if not passed else None, exceptions=exceptions,
        analysis_facts={"decision": decision, "persons": [
            {"name": r["person"], "passed": r["passed"], "reasons": r["reasons"]} for r in person_results],
            "exceptions": exceptions},
        fallback_reasoning=("All persons verified; identity documents valid and consistent."
                            if passed else "Identity-document exceptions flagged to Registry; DVO cannot clear."),
        fallback_insights=(["All passports valid ≥ 6 months and PoA within 92 days.",
                            "Face match cleared for every party.",
                            "No signature or name-consistency issues on signable documents."]
                           if passed else
                           [f"{e['person']}: {e['code']}" for e in exceptions][:5]),
    )


# ---------------------------------------------------------------- Compliance
def compute_compliance(company, people: list[Person], stage_docs: dict) -> StageOutcome:
    documents = stage_docs.get("compliance", [])
    risk = score(company, people)
    tier = risk["tier"]
    chain = escalation_chain(tier)
    preapproval = company.preapproval_status
    decision = "auto_approved" if not chain else "escalated"

    detail = {"tier": tier, "drivers": risk["drivers"], "escalation": chain,
              "preapproval_status": preapproval, "documents": documents}
    facts = {"decision": decision, "risk_tier": tier, "drivers": risk["drivers"],
             "escalation_chain": chain or "none", "preapproval_status": preapproval,
             "archetype": company.archetype, "premium": company.premium,
             "token_issuing": company.token_issuing, "documents": [d["doc_key"] for d in documents]}
    if chain:
        fb_reason = f"Risk tier {tier}. Escalated through {' → '.join(chain)} given the risk drivers."
        fb_insights = [f"Risk tier {tier} requires the full {' → '.join(chain)} chain.",
                       *[f"Driver: {d}" for d in risk["drivers"][:3]],
                       f"Pre-approval status: {preapproval or 'n/a'} (gate applied at R&L)."]
    else:
        fb_reason = f"Risk tier {tier}. Cleared at compliance-officer level; no escalation required."
        fb_insights = [f"Risk tier {tier} sits within the auto-approval threshold.",
                       "No PEP/sanctions or ownership-complexity escalators triggered.",
                       f"Pre-approval status: {preapproval or 'not applicable'}."]

    return StageOutcome(stage="compliance", decision=decision, detail=detail,
                        risk_score=_tier_score(tier), escalation_chain=chain,
                        analysis_facts=facts, fallback_reasoning=fb_reason, fallback_insights=fb_insights)


# ---------------------------------------------------------------- Lease
def compute_lease(company, run_id: str, stage_docs: dict) -> StageOutcome:
    documents = stage_docs.get("lease", [])
    fee = _fee_for(company.package)
    crm_ref = f"CRM-{company.sr.split('-')[-1]}"
    rec = LeaseRecord(company_id=company.id, run_id=run_id, package=company.package,
                      term="12 months", visa_quota=company.visa_quota, fee=fee,
                      crm_ref=crm_ref, status="created")
    detail = {"package": company.package, "term": "12 months", "visa_quota": company.visa_quota,
              "fee": fee, "crm_ref": crm_ref, "documents": documents}
    return StageOutcome(
        stage="lease", decision="passed", detail=detail, lease_record=rec,
        analysis_facts={"package": company.package, "term": "12 months", "visa_quota": company.visa_quota,
                        "fee": fee, "crm_ref": crm_ref, "documents": [d["doc_key"] for d in documents]},
        fallback_reasoning=(f"Lease provisioned for the {company.package} package at {fee} for a 12-month term; "
                            f"CRM record {crm_ref} created against confirmed payment."),
        fallback_insights=[f"Package {company.package} → fee {fee}.",
                           f"Visa quota {company.visa_quota} allocated for the term.",
                           "Payment confirmation (G03) on file; lease provisional until R&L clears."])


# ---------------------------------------------------------------- R&L / issuance
def compute_rnl(company, run_id: str, stage_docs: dict) -> StageOutcome:
    documents = stage_docs.get("rnl", [])
    premium = is_premium(company)
    preapproval = (company.preapproval_status or "").strip().lower()
    on_file = preapproval in _PREAPPROVAL_ON_FILE

    if premium and not on_file:
        reason = ("pre-approval pending" if preapproval == "pending"
                  else "pre-approval missing" if preapproval in ("missing", "")
                  else f"pre-approval status '{preapproval}' not on file")
        detail = {"gate": "blocked", "premium": True, "preapproval_status": company.preapproval_status,
                  "reason": reason, "documents": documents}
        return StageOutcome(
            stage="rnl", decision="blocked", detail=detail, terminal=True,
            final_status="blocked", company_status="blocked",
            analysis_facts={"decision": "blocked", "premium": True, "activity_class": company.activity_class,
                            "preapproval_status": company.preapproval_status, "reason": reason,
                            "documents": [d["doc_key"] for d in documents]},
            fallback_reasoning=f"Registry gate: premium activity requires regulator pre-approval; {reason}.",
            fallback_insights=[f"Activity '{company.activity_class}' is premium and gated at R&L.",
                               f"Pre-approval {company.preapproval_status or 'missing'} — cannot issue.",
                               "Resolve regulator pre-approval, then re-run to issue the licence."])

    n = company.sr.split("-")[-1]
    lic = License(company_id=company.id, run_id=run_id, cert_no=f"CoI-{company.sr}",
                  license_no=f"RAKDAO-L-{n}", establishment_card_no=f"EST-{n}", documents_visible=True)
    outputs = ["Certificate of Incorporation", "Trade License", "MOA", "Lease Agreement", "Establishment Card"]
    detail = {"gate": "passed", "cert_no": lic.cert_no, "license_no": lic.license_no,
              "establishment_card_no": lic.establishment_card_no, "documents_visible": True,
              "outputs": outputs, "documents": documents}
    return StageOutcome(
        stage="rnl", decision="passed", detail=detail, terminal=True,
        final_status="license_issued", company_status="license_issued", license=lic,
        analysis_facts={"decision": "license_issued", "premium": premium,
                        "preapproval_status": company.preapproval_status or "not required",
                        "license_no": lic.license_no, "outputs": outputs,
                        "documents": [d["doc_key"] for d in documents]},
        fallback_reasoning=("All prior stages cleared and the registry gate is satisfied; licence issued and "
                            "incorporation documents released."),
        fallback_insights=[f"Licence {lic.license_no} and establishment card {lic.establishment_card_no} issued.",
                           "No outstanding regulator pre-approval blocking issuance.",
                           "Incorporation document pack is now visible to the client."])


# ---------------------------------------------------------------- shared persistence
def persist_outcome(repo, run_id: str, company_id: str, outcome: StageOutcome, analysis: dict) -> None:
    detail = {**outcome.detail, "analysis": analysis, "narrative": analysis.get("reasoning")}
    repo.save_stage_result(run_id, StageResult(
        stage=outcome.stage, decision=outcome.decision, risk_score=outcome.risk_score,
        exceptions=outcome.exceptions, detail=detail))
    if outcome.lease_record:
        repo.save_lease(outcome.lease_record)
    if outcome.license:
        repo.save_license(outcome.license)
    if outcome.company_status:
        repo.set_company_status(company_id, outcome.company_status)
    repo.audit(company_id=company_id, run_id=run_id, actor="pipeline",
               action=f"{outcome.stage}_{outcome.decision}",
               payload={"decision": outcome.decision})


def record_verification(repo, company, run_id: str, final_status: str, reason: str = "") -> None:
    """Upsert the company's row in the verified/not-verified list on run completion."""
    repo.upsert_verification(
        company_id=company.id, sr=company.sr, name=company.name,
        status=final_status, verified=(final_status == "license_issued"),
        run_id=run_id, reason=reason)


def compute_stage(stage: str, ctx: dict) -> StageOutcome:
    """Dispatch a single stage compute using a context dict."""
    if stage == "dvo":
        return compute_dvo(ctx["company"], ctx["people"], ctx["pvs"], ctx["docs"], ctx["stage_docs"])
    if stage == "compliance":
        return compute_compliance(ctx["company"], ctx["people"], ctx["stage_docs"])
    if stage == "lease":
        return compute_lease(ctx["company"], ctx["run_id"], ctx["stage_docs"])
    if stage == "rnl":
        return compute_rnl(ctx["company"], ctx["run_id"], ctx["stage_docs"])
    raise ValueError(f"unknown stage {stage}")
