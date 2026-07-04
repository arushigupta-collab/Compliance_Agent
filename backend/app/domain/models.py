"""Canonical domain models — the shapes the app believes in.

These are what the API returns. Nothing DB-specific leaks upward; mappers.py
translates view rows into these models.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Company(BaseModel):
    id: str
    sr: str
    name: str
    archetype: str                # individual | corporate | dao
    company_type: str
    activity: str
    activity_class: str
    risk_tier: str
    jurisdiction: Optional[str] = None
    package: str
    visa_quota: int = 1
    premium: bool = False
    token_issuing: bool = False
    preapproval_status: Optional[str] = None
    status: str = "not_started"
    attributes: dict[str, Any] = Field(default_factory=dict)


class Person(BaseModel):
    id: str
    company_id: str
    name: str
    role: str
    nationality: Optional[str] = None
    dob: Optional[date] = None
    pob: Optional[str] = None
    passport_no: Optional[str] = None
    passport_issue: Optional[date] = None
    passport_expiry: Optional[date] = None
    issuing_authority: Optional[str] = None
    address: Optional[str] = None
    poa_source: Optional[str] = None
    poa_date: Optional[date] = None
    ubo_pct: Optional[str] = None
    is_ubo: bool = False
    is_signatory: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)


class DocumentRequirement(BaseModel):
    doc_key: str
    label: str
    source: str                   # generated | uploaded
    required: bool = True


class DocumentStatus(BaseModel):
    company_id: str
    doc_key: str
    source: str
    status: str = "missing"       # missing | uploaded | extracted
    filename: Optional[str] = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)


class ChecklistRow(BaseModel):
    """A requirement joined with its current upload status."""
    doc_key: str
    label: str
    source: str
    required: bool
    status: str = "missing"
    filename: Optional[str] = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)


class CompanyProfile(BaseModel):
    company: Company
    people: list[Person]
    checklist: list[ChecklistRow]
    passport_verifications: list["PassportVerification"] = Field(default_factory=list)
    can_run: bool = False
    run_blockers: list[str] = Field(default_factory=list)


class PassportVerification(BaseModel):
    id: Optional[str] = None
    company_id: str
    person_id: str
    person_name: Optional[str] = None
    passport_image_path: Optional[str] = None
    selfie_path: Optional[str] = None
    mrz: dict[str, Any] = Field(default_factory=dict)
    extracted: dict[str, Any] = Field(default_factory=dict)
    face_match_score: Optional[float] = None
    checks: dict[str, Any] = Field(default_factory=dict)
    overall: Optional[str] = None  # verified | flagged
    created_at: Optional[datetime] = None


class StageResult(BaseModel):
    stage: str                    # dvo | compliance | lease | rnl
    decision: str                 # passed | flagged | blocked | escalated | auto_approved
    risk_score: Optional[float] = None
    exceptions: list[Any] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class Escalation(BaseModel):
    id: Optional[str] = None
    level: str                    # officer | senior | director
    status: str = "pending"       # pending | approved | rejected
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None


class LeaseRecord(BaseModel):
    id: Optional[str] = None
    company_id: str
    run_id: Optional[str] = None
    package: Optional[str] = None
    term: Optional[str] = None
    visa_quota: Optional[int] = None
    fee: Optional[str] = None
    crm_ref: Optional[str] = None
    status: str = "created"


class License(BaseModel):
    id: Optional[str] = None
    company_id: str
    run_id: Optional[str] = None
    cert_no: Optional[str] = None
    license_no: Optional[str] = None
    establishment_card_no: Optional[str] = None
    documents_visible: bool = False
    issued_at: Optional[datetime] = None


class RunSummary(BaseModel):
    run_id: str
    company_id: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stages: list[StageResult] = Field(default_factory=list)
    escalations: list[Escalation] = Field(default_factory=list)


class AuditEntry(BaseModel):
    id: str
    company_id: Optional[str] = None
    run_id: Optional[str] = None
    actor: Optional[str] = None
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


CompanyProfile.model_rebuild()
