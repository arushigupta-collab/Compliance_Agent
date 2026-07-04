"""SupabaseRepository — hybrid: read company/people/docs live from the Supabase
customer-portal; keep every pipeline artifact in LOCAL Postgres (portal DB is
never written). To satisfy the existing local FKs, the Supabase company + its
people are mirrored (upserted) into the local companies/company_people tables on
demand — no schema change required.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from sqlalchemy import text

from app import supabase_client as sb
from app import supabase_map as smap
from app.db.session import session_scope
from app.domain.models import (
    Company, DocumentStatus, Escalation, LeaseRecord, License,
    PassportVerification, Person, RunSummary, StageResult,
)
from app.repo.local_repo import LocalRepository


class SupabaseRepository:
    def __init__(self):
        self._local = LocalRepository()

    # ---------------- Supabase reads ----------------
    @lru_cache(maxsize=1)
    def _packages(self) -> dict[str, dict]:
        return {str(p["id"]): p for p in sb.select("packages")}

    def _local_statuses(self) -> dict[str, str]:
        with session_scope() as s:
            return {str(r._mapping["id"]): r._mapping["status"]
                    for r in s.execute(text("select id, status from companies"))}

    def list_companies(self) -> list[Company]:
        rows = sb.select("customer_portal", order="created_at.desc")
        pkgs, statuses = self._packages(), self._local_statuses()
        return [smap.company_from_portal(r, pkgs.get(str(r.get("package_id"))),
                                         statuses.get(str(r["id"]), "not_started")) for r in rows]

    def _company(self, row: dict) -> Company:
        status = self._local_statuses().get(str(row["id"]), "not_started")
        return smap.company_from_portal(row, self._packages().get(str(row.get("package_id"))), status)

    def get_company(self, sr: str) -> Optional[Company]:
        row = sb.get_one("customer_portal", sr)
        return self._company(row) if row else None

    def get_company_by_id(self, company_id: str) -> Optional[Company]:
        return self.get_company(company_id)

    def get_people(self, company_id: str) -> list[Person]:
        shs = sb.select("shareholders", filters={"application_id": f"eq.{company_id}"}, order="created_at.asc")
        poa = sb.select("documents", filters={"application_id": f"eq.{company_id}", "type_key": "eq.address_proof"})
        poa_by = {str(d.get("shareholder_id")): (d.get("uploaded_at") or "")[:10] for d in poa}
        people = [smap.person_from_shareholder(sh, poa_by.get(str(sh["id"]))) for sh in shs]
        self._mirror(company_id, people)
        return people

    def get_document_status(self, company_id: str) -> list[DocumentStatus]:
        docs = sb.select("documents", filters={"application_id": f"eq.{company_id}"})
        return [smap.doc_status_from_document(d) for d in docs]

    def requirements_meta(self, domain: str):
        """Fetch (required_document_types, form_templates) for the Supabase checklist."""
        return sb.select("required_document_types"), sb.select("form_templates")

    # ---------------- mirror Supabase → local (for FK integrity) ----------------
    def _mirror(self, company_id: str, people: Optional[list[Person]] = None) -> None:
        row = sb.get_one("customer_portal", company_id)
        if not row:
            return
        c = self._company(row)
        with session_scope() as s:
            s.execute(text("""
                insert into companies (id, sr, name, archetype, company_type, activity, activity_class,
                    risk_tier, jurisdiction, package, visa_quota, premium, token_issuing, preapproval_status,
                    status, attributes)
                values (:id,:sr,:name,:arch,:ct,:act,:ac,:rt,:jur,:pkg,:vq,:prem,:tok,:pre,'not_started',cast(:attr as jsonb))
                on conflict (id) do update set
                    name=excluded.name, archetype=excluded.archetype, company_type=excluded.company_type,
                    activity=excluded.activity, activity_class=excluded.activity_class, risk_tier=excluded.risk_tier,
                    jurisdiction=excluded.jurisdiction, package=excluded.package, visa_quota=excluded.visa_quota,
                    premium=excluded.premium, token_issuing=excluded.token_issuing,
                    preapproval_status=excluded.preapproval_status, attributes=excluded.attributes
            """), dict(id=c.id, sr=c.sr, name=c.name, arch=c.archetype, ct=c.company_type, act=c.activity,
                       ac=c.activity_class, rt=c.risk_tier, jur=c.jurisdiction, pkg=c.package, vq=c.visa_quota,
                       prem=c.premium, tok=c.token_issuing, pre=c.preapproval_status, attr=json.dumps(c.attributes)))
            if people is None:
                shs = sb.select("shareholders", filters={"application_id": f"eq.{company_id}"})
                people = [smap.person_from_shareholder(sh, None) for sh in shs]
            for p in people:
                s.execute(text("""
                    insert into company_people (id, company_id, name, role, nationality, dob, passport_no,
                        passport_issue, passport_expiry, issuing_authority, address, poa_source, poa_date,
                        ubo_pct, is_ubo, is_signatory, attributes)
                    values (:id,:cid,:name,:role,:nat,:dob,:pno,:pi,:pe,:ia,:addr,:ps,:pd,:ubo,:isu,:iss,cast(:attr as jsonb))
                    on conflict (id) do update set
                        name=excluded.name, role=excluded.role, nationality=excluded.nationality, dob=excluded.dob,
                        passport_no=excluded.passport_no, passport_issue=excluded.passport_issue,
                        passport_expiry=excluded.passport_expiry, issuing_authority=excluded.issuing_authority,
                        address=excluded.address, poa_source=excluded.poa_source, poa_date=excluded.poa_date,
                        ubo_pct=excluded.ubo_pct, is_ubo=excluded.is_ubo, is_signatory=excluded.is_signatory,
                        attributes=excluded.attributes
                """), dict(id=p.id, cid=p.company_id, name=p.name, role=p.role, nat=p.nationality, dob=p.dob,
                           pno=p.passport_no, pi=p.passport_issue, pe=p.passport_expiry, ia=p.issuing_authority,
                           addr=p.address, ps=p.poa_source, pd=p.poa_date, ubo=p.ubo_pct, isu=p.is_ubo,
                           iss=p.is_signatory, attr=json.dumps(p.attributes)))

    # ---------------- pipeline reads/writes → LOCAL (mirror first where needed) ----------------
    def get_passport_verifications(self, company_id: str) -> list[PassportVerification]:
        return self._local.get_passport_verifications(company_id)

    def get_run(self, run_id: str) -> Optional[RunSummary]:
        return self._local.get_run(run_id)

    def get_escalations(self, run_id: str) -> list[Escalation]:
        return self._local.get_escalations(run_id)

    def get_lease(self, company_id: str) -> Optional[LeaseRecord]:
        return self._local.get_lease(company_id)

    def get_license(self, company_id: str) -> Optional[License]:
        return self._local.get_license(company_id)

    def get_audit(self, company_id: str) -> list[dict[str, Any]]:
        return self._local.get_audit(company_id)

    def list_verifications(self) -> list[dict[str, Any]]:
        return self._local.list_verifications()

    def upsert_upload(self, *a, **k) -> None:
        self._local.upsert_upload(*a, **k)

    def save_passport_verification(self, pv: PassportVerification) -> str:
        self._mirror(pv.company_id)
        return self._local.save_passport_verification(pv)

    def create_run(self, company_id: str) -> str:
        self._mirror(company_id)
        return self._local.create_run(company_id)

    def finish_run(self, *a, **k) -> None:
        self._local.finish_run(*a, **k)

    def save_stage_result(self, *a, **k) -> None:
        self._local.save_stage_result(*a, **k)

    def create_escalation(self, *a, **k) -> str:
        return self._local.create_escalation(*a, **k)

    def set_escalation(self, *a, **k) -> None:
        self._local.set_escalation(*a, **k)

    def save_lease(self, rec: LeaseRecord) -> None:
        self._local.save_lease(rec)

    def save_license(self, lic: License) -> None:
        self._local.save_license(lic)

    def set_company_status(self, company_id: str, status: str) -> None:
        self._mirror(company_id)
        self._local.set_company_status(company_id, status)

    def upsert_verification(self, *a, **k) -> None:
        self._local.upsert_verification(*a, **k)

    def audit(self, **kw) -> None:
        self._local.audit(**kw)
