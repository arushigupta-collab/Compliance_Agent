"""Versioned API (/api/v1). All responses are domain models."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.deps import get_repository, get_storage
from app.domain.models import (
    AuditEntry,
    Company,
    CompanyProfile,
    LeaseRecord,
    License,
    PassportVerification,
    RunSummary,
)
from app.services import build_profile
from app.storage.base import PASSPORT_IMAGES, RAW_DOCUMENTS, SELFIES

router = APIRouter()


def _company_or_404(sr: str) -> Company:
    c = get_repository().get_company(sr)
    if not c:
        raise HTTPException(status_code=404, detail=f"Company {sr} not found")
    return c


@router.get("/companies", response_model=list[Company])
def list_companies() -> list[Company]:
    return get_repository().list_companies()


@router.get("/companies/{sr}", response_model=CompanyProfile)
def get_company_profile(sr: str) -> CompanyProfile:
    profile = build_profile(sr)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Company {sr} not found")
    return profile


@router.get("/files/{path:path}")
def get_file(path: str):
    """Serve a stored file from the local storage root."""
    full = Path(settings.storage_root) / path
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(full))


# ---------------------------------------------------------------- Documents
class DocumentUploadResult(BaseModel):
    doc_key: str
    status: str
    filename: str
    storage_path: str
    extracted_fields: dict


@router.post("/companies/{sr}/documents", response_model=DocumentUploadResult)
async def upload_document(sr: str, doc_key: str = Form(...), source: str = Form("uploaded"),
                          seed_path: Optional[str] = Form(None),
                          file: Optional[UploadFile] = File(None)) -> DocumentUploadResult:
    """Upload a file (or pick one from seed-documents via seed_path), store it,
    run extraction, and upsert the document_uploads row."""
    from app.extract import extract_fields

    company = _company_or_404(sr)
    repo, storage = get_repository(), get_storage()

    if file is not None:
        data = await file.read()
        filename = file.filename or f"{doc_key}.pdf"
    elif seed_path:
        src = (Path(settings.dataset_root) / seed_path) if not Path(seed_path).is_absolute() else Path(seed_path)
        if not src.exists():
            raise HTTPException(status_code=400, detail=f"Seed document not found: {seed_path}")
        data = src.read_bytes()
        filename = src.name
    else:
        raise HTTPException(status_code=400, detail="Provide either a file or seed_path")

    key = f"{company.id}/{doc_key}_{filename}"
    storage_path = storage.put(RAW_DOCUMENTS, key, data)

    # Extract from the stored file (write to a temp path if needed).
    stored_abs = Path(settings.storage_root) / storage_path
    try:
        fields = extract_fields(stored_abs, doc_key)
    except Exception:
        fields = {"_kind": "unparsed"}

    repo.upsert_upload(company.id, doc_key, source, filename, storage_path, fields, "extracted")
    repo.audit(company_id=company.id, actor="operator", action="document_uploaded",
               payload={"doc_key": doc_key, "filename": filename})
    return DocumentUploadResult(doc_key=doc_key, status="extracted", filename=filename,
                                storage_path=storage_path, extracted_fields=fields)


class SeedLoadResult(BaseModel):
    loaded: int
    doc_keys: list[str]


@router.post("/companies/{sr}/load-seed-documents", response_model=SeedLoadResult)
def load_seed_documents(sr: str) -> SeedLoadResult:
    """Demo convenience: load this company's dataset documents (from _INDEX.csv)
    into storage + document_uploads with extraction, in one click."""
    import csv

    from app.extract import extract_fields

    company = _company_or_404(sr)
    repo, storage = get_repository(), get_storage()
    root = Path(settings.dataset_root)

    loaded: list[str] = []
    with open(settings.dataset_index, newline="") as f:
        for row in csv.DictReader(f):
            if row["SR"] != sr:
                continue
            doc_key = row["Code"]
            src = root / row["Relative path"]
            if not src.exists():
                continue
            data = src.read_bytes()
            key = f"{company.id}/{doc_key}_{src.name}"
            storage_path = storage.put(RAW_DOCUMENTS, key, data)
            try:
                fields = extract_fields(Path(settings.storage_root) / storage_path, doc_key)
            except Exception:
                fields = {"_kind": "unparsed"}
            source = "generated" if row["Source"] == "GENERATED" else "uploaded"
            repo.upsert_upload(company.id, doc_key, source, src.name, storage_path, fields, "extracted")
            loaded.append(doc_key)

    repo.audit(company_id=company.id, actor="operator", action="seed_documents_loaded",
               payload={"count": len(loaded)})
    return SeedLoadResult(loaded=len(loaded), doc_keys=sorted(loaded))


# ---------------------------------------------------------------- Passport verification
@router.post("/companies/{sr}/passport-verifications", response_model=PassportVerification)
async def create_passport_verification(
    sr: str, person_id: str = Form(...),
    passport_image: Optional[UploadFile] = File(None),
    selfie: Optional[UploadFile] = File(None),
) -> PassportVerification:
    from app.extract import to_date
    from app.vision import face, passport

    company = _company_or_404(sr)
    repo, storage = get_repository(), get_storage()
    people = {p.id: p for p in repo.get_people(company.id)}
    person = people.get(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    def _abs(p: str) -> str:
        return str(Path(settings.storage_root) / p)

    passport_path = selfie_path = None
    passport_face_path = None       # image used for face detection (rasterized if PDF)
    uploaded_fields: dict = {}       # passport fields read from an uploaded PDF

    # The passport may arrive as a PDF or an image (png/jpg). A PDF is rasterized
    # to a page image for face detection, and its text fields drive validity.
    if passport_image is not None:
        data = await passport_image.read()
        fname = passport_image.filename or "passport"
        passport_path = storage.put(PASSPORT_IMAGES, f"{company.id}/{person_id}_passport_{fname}", data)
        if passport.is_pdf(fname, passport_image.content_type):
            uploaded_fields = passport.passport_fields_from_pdf(_abs(passport_path))
            png = passport.rasterize_pdf_first_page(_abs(passport_path))
            if png:
                passport_face_path = storage.put(
                    PASSPORT_IMAGES, f"{company.id}/{person_id}_passport_render.png", png)
        else:
            passport_face_path = passport_path  # already an image
    if selfie is not None:
        selfie_path = storage.put(SELFIES, f"{company.id}/{person_id}_selfie_{selfie.filename}", await selfie.read())

    # (2) Passport validity — prefer the expiry read from the uploaded passport,
    # fall back to the seeded record. Name (when read) feeds the name-match check.
    expiry = to_date(uploaded_fields.get("passport_expiry")) or person.passport_expiry
    doc_name = uploaded_fields.get("name")
    checks = passport.field_checks(expiry=expiry, poa_date=person.poa_date,
                                   doc_name=doc_name, person_name=person.name, mrz_valid=True)

    # (1) Face match against the live photo. Use the real OpenCV result only when a
    # score is produced (faces detected in both); otherwise fall back deterministically
    # (synthetic passport PDFs carry no photo).
    face_res = None
    if passport_face_path and selfie_path and face.models_available():
        r = face.match_faces(
            _abs(passport_face_path), _abs(selfie_path),
            crop_out_dir=str(Path(settings.storage_root) / "generated-outputs" / company.id / person_id),
        )
        if r.get("face_match_score") is not None:
            face_res = r
    if face_res is None:
        face_res = face.fallback_match(checks["passed"])

    all_checks = {**checks, **{f"face_{k}": v for k, v in face_res.items()}}
    overall = "verified" if (checks["passed"] and face_res.get("passed")) else "flagged"
    pv = PassportVerification(
        company_id=company.id, person_id=person_id, person_name=person.name,
        passport_image_path=passport_path, selfie_path=selfie_path,
        mrz=uploaded_fields,
        extracted={"name": doc_name or person.name, "expiry": str(expiry),
                   "poa_date": str(person.poa_date),
                   "passport_source": "uploaded_pdf" if uploaded_fields else "image_or_seeded"},
        face_match_score=face_res.get("face_match_score"), checks=all_checks, overall=overall,
    )
    pv.id = repo.save_passport_verification(pv)
    repo.audit(company_id=company.id, actor="operator", action="passport_verification",
               payload={"person": person.name, "overall": overall,
                        "score": face_res.get("face_match_score"),
                        "passport_format": "pdf" if uploaded_fields else "image"})
    return pv


# ---------------------------------------------------------------- Runs
class RunCreated(BaseModel):
    run_id: str


@router.post("/companies/{sr}/runs", response_model=RunCreated)
def start_run(sr: str) -> RunCreated:
    """Create a run. Stages are NOT executed here — each stage runs lazily when
    its page is reached, via GET /runs/{id}/stages/{stage}/stream."""
    company = _company_or_404(sr)
    repo = get_repository()
    run_id = repo.create_run(company.id)
    repo.set_company_status(company.id, "in_review")
    repo.audit(company_id=company.id, run_id=run_id, actor="operator", action="run_created", payload={})
    return RunCreated(run_id=run_id)


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(run_id: str) -> RunSummary:
    run = get_repository().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


class EscalationDecision(BaseModel):
    status: str  # approved | rejected
    decided_by: str = "operator"


@router.post("/runs/{run_id}/escalations/{level}")
def decide_escalation(run_id: str, level: str, body: EscalationDecision) -> dict:
    repo = get_repository()
    repo.set_escalation(run_id, level, body.status, body.decided_by)
    repo.audit(run_id=run_id, actor=body.decided_by, action="escalation_decision",
               payload={"level": level, "status": body.status})
    return {"run_id": run_id, "level": level, "status": body.status}


# ---------------------------------------------------------------- Lease / License / Audit
@router.get("/companies/{sr}/lease", response_model=Optional[LeaseRecord])
def get_lease(sr: str) -> Optional[LeaseRecord]:
    company = _company_or_404(sr)
    return get_repository().get_lease(company.id)


@router.get("/companies/{sr}/license", response_model=Optional[License])
def get_license(sr: str) -> Optional[License]:
    company = _company_or_404(sr)
    return get_repository().get_license(company.id)


@router.get("/companies/{sr}/audit", response_model=list[AuditEntry])
def get_audit(sr: str) -> list[AuditEntry]:
    company = _company_or_404(sr)
    return [AuditEntry(**row) for row in get_repository().get_audit(company.id)]


@router.get("/companies/{sr}/audit/report")
def get_audit_report(sr: str):
    """Generate the full compliance audit report as a downloadable PDF."""
    from fastapi.responses import Response

    from app.report import build_audit_report

    repo = get_repository()
    company = _company_or_404(sr)
    people = repo.get_people(company.id)
    pvs = repo.get_passport_verifications(company.id)
    audit = repo.get_audit(company.id)
    lease = repo.get_lease(company.id)
    lic = repo.get_license(company.id)
    # latest run for this company
    run = None
    verif = next((v for v in repo.list_verifications() if v["company_id"] == company.id), None)
    if verif and verif.get("last_run_id"):
        run = repo.get_run(verif["last_run_id"])
    pdf = build_audit_report(company=company, people=people, pvs=pvs, run=run,
                             lease=lease, license=lic, audit=audit)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="audit-report-{sr}.pdf"'})


# ---------------------------------------------------------------- Verifications list
@router.get("/verifications")
def list_verifications() -> list[dict]:
    """The DB list of which companies are verified or not (one row per run company)."""
    return get_repository().list_verifications()
