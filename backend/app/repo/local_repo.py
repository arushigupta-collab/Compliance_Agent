"""LocalRepository: SQLAlchemy over local Postgres.

Reads go through the v_* views (the contract seam); writes go to base tables.
Uses raw SQL via SQLAlchemy Core text() to keep the view-reading explicit.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text

from app.db.session import session_scope
from app.domain.models import (
    Company,
    DocumentStatus,
    Escalation,
    LeaseRecord,
    License,
    PassportVerification,
    Person,
    RunSummary,
    StageResult,
)
from app.mappers import company_from_row, document_status_from_row, person_from_row


def _rows(s, sql: str, **params) -> list[dict[str, Any]]:
    res = s.execute(text(sql), params)
    return [dict(r._mapping) for r in res]


def _one(s, sql: str, **params) -> Optional[dict[str, Any]]:
    rows = _rows(s, sql, **params)
    return rows[0] if rows else None


class LocalRepository:
    # ---------- Reads (v_* views) ----------
    def list_companies(self) -> list[Company]:
        with session_scope() as s:
            return [company_from_row(r) for r in _rows(s, "select * from v_companies order by sr")]

    def get_company(self, sr: str) -> Optional[Company]:
        with session_scope() as s:
            row = _one(s, "select * from v_companies where sr = :sr", sr=sr)
            return company_from_row(row) if row else None

    def get_company_by_id(self, company_id: str) -> Optional[Company]:
        with session_scope() as s:
            row = _one(s, "select * from v_companies where id = :id", id=company_id)
            return company_from_row(row) if row else None

    def get_people(self, company_id: str) -> list[Person]:
        with session_scope() as s:
            return [person_from_row(r) for r in _rows(
                s, "select * from v_company_people where company_id = :cid order by name", cid=company_id)]

    def get_document_status(self, company_id: str) -> list[DocumentStatus]:
        with session_scope() as s:
            return [document_status_from_row(r) for r in _rows(
                s, "select * from v_document_status where company_id = :cid", cid=company_id)]

    def get_passport_verifications(self, company_id: str) -> list[PassportVerification]:
        with session_scope() as s:
            rows = _rows(s, """
                select pv.*, p.name as person_name
                from passport_verifications pv
                join company_people p on p.id = pv.person_id
                where pv.company_id = :cid order by pv.created_at
            """, cid=company_id)
        return [PassportVerification(
            id=str(r["id"]), company_id=str(r["company_id"]), person_id=str(r["person_id"]),
            person_name=r.get("person_name"),
            passport_image_path=r.get("passport_image_path"), selfie_path=r.get("selfie_path"),
            mrz=r.get("mrz") or {}, extracted=r.get("extracted") or {},
            face_match_score=float(r["face_match_score"]) if r.get("face_match_score") is not None else None,
            checks=r.get("checks") or {}, overall=r.get("overall"), created_at=r.get("created_at"),
        ) for r in rows]

    def get_run(self, run_id: str) -> Optional[RunSummary]:
        with session_scope() as s:
            row = _one(s, "select * from v_run_summary where run_id = :rid", rid=run_id)
            if not row:
                return None
            stages_raw = row.get("stages") or []
            if isinstance(stages_raw, str):
                stages_raw = json.loads(stages_raw)
            stages = [StageResult(
                stage=st["stage"], decision=st["decision"],
                risk_score=st.get("risk"), exceptions=st.get("exceptions") or [],
                detail=st.get("detail") or {},
            ) for st in stages_raw]
            escalations = self.get_escalations(run_id)
            return RunSummary(
                run_id=str(row["run_id"]), company_id=str(row["company_id"]),
                status=row["status"], started_at=row.get("started_at"),
                finished_at=row.get("finished_at"), stages=stages, escalations=escalations,
            )

    def get_escalations(self, run_id: str) -> list[Escalation]:
        with session_scope() as s:
            rows = _rows(s, "select * from escalations where run_id = :rid order by "
                            "case level when 'officer' then 1 when 'senior' then 2 else 3 end", rid=run_id)
        return [Escalation(id=str(r["id"]), level=r["level"], status=r["status"],
                           decided_by=r.get("decided_by"), decided_at=r.get("decided_at")) for r in rows]

    def get_lease(self, company_id: str) -> Optional[LeaseRecord]:
        with session_scope() as s:
            r = _one(s, "select * from lease_records where company_id = :cid order by created_at desc limit 1", cid=company_id)
        if not r:
            return None
        return LeaseRecord(id=str(r["id"]), company_id=str(r["company_id"]),
                           run_id=str(r["run_id"]) if r.get("run_id") else None,
                           package=r.get("package"), term=r.get("term"), visa_quota=r.get("visa_quota"),
                           fee=r.get("fee"), crm_ref=r.get("crm_ref"), status=r.get("status") or "created")

    def get_license(self, company_id: str) -> Optional[License]:
        with session_scope() as s:
            r = _one(s, "select * from licenses where company_id = :cid order by issued_at desc nulls last limit 1", cid=company_id)
        if not r:
            return None
        return License(id=str(r["id"]), company_id=str(r["company_id"]),
                       run_id=str(r["run_id"]) if r.get("run_id") else None,
                       cert_no=r.get("cert_no"), license_no=r.get("license_no"),
                       establishment_card_no=r.get("establishment_card_no"),
                       documents_visible=bool(r.get("documents_visible")), issued_at=r.get("issued_at"))

    def get_audit(self, company_id: str) -> list[dict[str, Any]]:
        with session_scope() as s:
            rows = _rows(s, "select * from audit_log where company_id = :cid order by created_at", cid=company_id)
        for r in rows:
            r["id"] = str(r["id"])
            if r.get("company_id"):
                r["company_id"] = str(r["company_id"])
            if r.get("run_id"):
                r["run_id"] = str(r["run_id"])
        return rows

    # ---------- Writes (base tables) ----------
    def upsert_upload(self, company_id: str, doc_key: str, source: str, filename: str,
                      path: str, fields: dict, status: str) -> None:
        with session_scope() as s:
            s.execute(text("""
                insert into document_uploads (company_id, doc_key, source, filename, storage_path, status, extracted_fields)
                values (:cid, :dk, :src, :fn, :sp, :st, cast(:ef as jsonb))
                on conflict (company_id, doc_key) do update
                set source=excluded.source, filename=excluded.filename, storage_path=excluded.storage_path,
                    status=excluded.status, extracted_fields=excluded.extracted_fields
            """), dict(cid=company_id, dk=doc_key, src=source, fn=filename, sp=path,
                       st=status, ef=json.dumps(fields)))

    def save_passport_verification(self, pv: PassportVerification) -> str:
        with session_scope() as s:
            row = _one(s, """
                insert into passport_verifications
                  (company_id, person_id, passport_image_path, selfie_path, mrz, extracted, face_match_score, checks, overall)
                values (:cid, :pid, :pip, :sp, cast(:mrz as jsonb), cast(:ex as jsonb), :fms, cast(:ck as jsonb), :ov)
                returning id
            """, cid=pv.company_id, pid=pv.person_id, pip=pv.passport_image_path, sp=pv.selfie_path,
                mrz=json.dumps(pv.mrz), ex=json.dumps(pv.extracted), fms=pv.face_match_score,
                ck=json.dumps(pv.checks), ov=pv.overall)
            return str(row["id"])

    def create_run(self, company_id: str) -> str:
        with session_scope() as s:
            row = _one(s, "insert into compliance_runs (company_id) values (:cid) returning id", cid=company_id)
            return str(row["id"])

    def finish_run(self, run_id: str, status: str, summary: dict) -> None:
        with session_scope() as s:
            s.execute(text("update compliance_runs set status=:st, finished_at=now(), summary=cast(:sm as jsonb) where id=:rid"),
                      dict(st=status, sm=json.dumps(summary), rid=run_id))

    def save_stage_result(self, run_id: str, sr: StageResult) -> None:
        with session_scope() as s:
            s.execute(text("""
                insert into stage_results (run_id, stage, decision, risk_score, exceptions, detail)
                values (:rid, :stg, :dec, :rs, cast(:ex as jsonb), cast(:dt as jsonb))
            """), dict(rid=run_id, stg=sr.stage, dec=sr.decision, rs=sr.risk_score,
                       ex=json.dumps(sr.exceptions), dt=json.dumps(sr.detail)))

    def create_escalation(self, run_id: str, level: str) -> str:
        with session_scope() as s:
            row = _one(s, "insert into escalations (run_id, level) values (:rid, :lv) returning id", rid=run_id, lv=level)
            return str(row["id"])

    def set_escalation(self, run_id: str, level: str, status: str, by: str) -> None:
        with session_scope() as s:
            s.execute(text("""
                update escalations set status=:st, decided_by=:by, decided_at=now()
                where run_id=:rid and level=:lv
            """), dict(st=status, by=by, rid=run_id, lv=level))

    def save_lease(self, rec: LeaseRecord) -> None:
        with session_scope() as s:
            s.execute(text("""
                insert into lease_records (company_id, run_id, package, term, visa_quota, fee, crm_ref, status)
                values (:cid, :rid, :pkg, :term, :vq, :fee, :crm, :st)
            """), dict(cid=rec.company_id, rid=rec.run_id, pkg=rec.package, term=rec.term,
                       vq=rec.visa_quota, fee=rec.fee, crm=rec.crm_ref, st=rec.status))

    def save_license(self, lic: License) -> None:
        with session_scope() as s:
            s.execute(text("""
                insert into licenses (company_id, run_id, cert_no, license_no, establishment_card_no, documents_visible, issued_at)
                values (:cid, :rid, :cert, :lic, :est, :dv, now())
            """), dict(cid=lic.company_id, rid=lic.run_id, cert=lic.cert_no, lic=lic.license_no,
                       est=lic.establishment_card_no, dv=lic.documents_visible))

    def set_company_status(self, company_id: str, status: str) -> None:
        with session_scope() as s:
            s.execute(text("update companies set status=:st where id=:cid"), dict(st=status, cid=company_id))

    def upsert_verification(self, company_id: str, sr: str, name: str, status: str,
                            verified: bool, run_id: str, reason: str) -> None:
        with session_scope() as s:
            s.execute(text("""
                insert into company_verifications (company_id, sr, name, status, verified, last_run_id, reason, decided_at)
                values (:cid, :sr, :name, :st, :ver, :rid, :reason, now())
                on conflict (company_id) do update
                set sr=excluded.sr, name=excluded.name, status=excluded.status, verified=excluded.verified,
                    last_run_id=excluded.last_run_id, reason=excluded.reason, decided_at=now()
            """), dict(cid=company_id, sr=sr, name=name, st=status, ver=verified, rid=run_id, reason=reason))

    def list_verifications(self) -> list[dict[str, Any]]:
        with session_scope() as s:
            rows = _rows(s, "select * from company_verifications order by decided_at desc")
        for r in rows:
            r["company_id"] = str(r["company_id"])
            if r.get("last_run_id"):
                r["last_run_id"] = str(r["last_run_id"])
        return rows

    def audit(self, **kw) -> None:
        with session_scope() as s:
            s.execute(text("""
                insert into audit_log (company_id, run_id, actor, action, payload)
                values (:cid, :rid, :actor, :action, cast(:payload as jsonb))
            """), dict(cid=kw.get("company_id"), rid=kw.get("run_id"), actor=kw.get("actor", "operator"),
                       action=kw["action"], payload=json.dumps(kw.get("payload", {}))))
