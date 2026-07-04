"""Seed 15 companies (upsert on sr) + their people.

Company-level facts come from spec §6/§9 (hardcoded here — they are the
compliance ground truth). Person rows are DERIVED from the real uploaded
passport/PoA PDFs so the DVO defect values (Fireblocks expiry, Jupiter
expiry + stale PoA) come straight from the dataset, not hand-typed.

Idempotent: re-running upserts companies and rebuilds their people.
Does NOT seed document_uploads (the operator supplies uploads in the demo).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# Make `app` importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.extract import extract_fields, to_date  # noqa: E402
from app.rules.checklist import required_documents  # noqa: E402
from app.domain.models import Company  # noqa: E402

DATASET = Path(settings.dataset_root)


# ---- Company facts (spec §6 / §9 ground truth) ----
# fields: sr, name, folder, archetype, company_type, activity, activity_class,
#         risk_tier, jurisdiction, package, visa_quota, premium, token_issuing,
#         preapproval_status, attributes
COMPANIES = [
    # Archetype A — Individual (clean, non-premium)
    dict(sr="SR-2026-01042", name="Sarvam AI (RAK) FZ-LLC", folder="SR-2026-01042_Sarvam_AI__RAK__FZ_LLC",
         archetype="individual", company_type="FZ-LLC", activity="AI / LLM software development (Indic languages)",
         activity_class="Non-premium (technology / software)", risk_tier="LOW",
         jurisdiction="RAK DAO", package="Flexi-desk (Standard)", visa_quota=2,
         premium=False, token_issuing=False, preapproval_status=None, attributes={}),
    dict(sr="SR-2026-01043", name="Krutrim MENA FZ-LLC", folder="SR-2026-01043_Krutrim_MENA_FZ_LLC",
         archetype="individual", company_type="FZ-LLC", activity="AI / foundational models",
         activity_class="Non-premium (technology / software)", risk_tier="LOW",
         jurisdiction="RAK DAO", package="Flexi-desk (Standard)", visa_quota=2,
         premium=False, token_issuing=False, preapproval_status=None, attributes={}),
    dict(sr="SR-2026-01044", name="Ati Motors (RAK) FZ-LLC", folder="SR-2026-01044_Ati_Motors__RAK__FZ_LLC",
         archetype="individual", company_type="FZ-LLC", activity="Autonomous mobile robotics",
         activity_class="Non-premium (technology / robotics)", risk_tier="LOW-MEDIUM",
         jurisdiction="RAK DAO", package="Flexi-desk (Standard)", visa_quota=2,
         premium=False, token_issuing=False, preapproval_status=None, attributes={}),
    dict(sr="SR-2026-01045", name="GenRobotics MENA FZ-LLC", folder="SR-2026-01045_GenRobotics_MENA_FZ_LLC",
         archetype="individual", company_type="FZ-LLC", activity="Robotics for sanitation / infrastructure",
         activity_class="Non-premium (technology / robotics)", risk_tier="LOW-MEDIUM",
         jurisdiction="RAK DAO", package="Flexi-desk (Standard)", visa_quota=2,
         premium=False, token_issuing=False, preapproval_status=None, attributes={}),
    dict(sr="SR-2026-01046", name="HealthifyMe (RAK) FZ-LLC", folder="SR-2026-01046_HealthifyMe__RAK__FZ_LLC",
         archetype="individual", company_type="FZ-LLC", activity="Digital health / wellness platform",
         activity_class="Non-premium (technology / health-tech)", risk_tier="LOW-MEDIUM",
         jurisdiction="RAK DAO", package="Flexi-desk (Standard)", visa_quota=2,
         premium=False, token_issuing=False, preapproval_status=None,
         attributes={"co_note": "Scope note: health-tech activity confirmed within permitted classification; no escalation."}),

    # Archetype B — Corporate subsidiary
    dict(sr="SR-2026-02011", name="Fireblocks MENA FZ-LLC", folder="SR-2026-02011_Fireblocks_MENA_FZ_LLC",
         archetype="corporate", company_type="FZ-LLC", activity="Digital-asset custody technology",
         activity_class="PREMIUM (digital-asset custody)", risk_tier="HIGH",
         jurisdiction="RAK DAO", package="Standard office / 6", visa_quota=6,
         premium=True, token_issuing=False, preapproval_status="missing",
         attributes={"parent": {"name": "Fireblocks Ltd", "reg_country": "United States",
                                "reg_no": "US-DE-6620114", "incorp_date": "2018-01-10", "good_standing": True}}),
    dict(sr="SR-2026-02012", name="Cohere MENA FZ-LLC", folder="SR-2026-02012_Cohere_MENA_FZ_LLC",
         archetype="corporate", company_type="FZ-LLC", activity="Enterprise LLM / NLP platform",
         activity_class="Non-premium (technology / software)", risk_tier="MEDIUM",
         jurisdiction="RAK DAO", package="Standard office / 4", visa_quota=4,
         premium=False, token_issuing=False, preapproval_status=None,
         attributes={"parent": {"name": "Cohere Inc.", "reg_country": "Canada",
                                "reg_no": "CA-ON-100294", "incorp_date": "2019-06-01", "good_standing": True}}),
    dict(sr="SR-2026-02013", name="Mistral MENA FZ-LLC", folder="SR-2026-02013_Mistral_MENA_FZ_LLC",
         archetype="corporate", company_type="FZ-LLC", activity="Open-weight LLM development",
         activity_class="Non-premium (technology / software)", risk_tier="MEDIUM",
         jurisdiction="RAK DAO", package="Standard office / 4", visa_quota=4,
         premium=False, token_issuing=False, preapproval_status=None,
         attributes={"parent": {"name": "Mistral AI SAS", "reg_country": "France",
                                "reg_no": "FR-RCS-914912", "incorp_date": "2023-04-28", "good_standing": True}}),
    dict(sr="SR-2026-02014", name="Krafton MENA FZ-LLC", folder="SR-2026-02014_Krafton_MENA_FZ_LLC",
         archetype="corporate", company_type="FZ-LLC", activity="Online gaming / publishing",
         activity_class="PREMIUM (online gaming)", risk_tier="MEDIUM-HIGH",
         jurisdiction="RAK DAO", package="Standard office / 8", visa_quota=8,
         premium=True, token_issuing=False, preapproval_status="missing",
         attributes={"parent": {"name": "KRAFTON, Inc.", "reg_country": "South Korea",
                                "reg_no": "KR-SEL-2007-441", "incorp_date": "2007-03-26", "good_standing": True}}),
    dict(sr="SR-2026-02015", name="Immutable MENA FZ-LLC", folder="SR-2026-02015_Immutable_MENA_FZ_LLC",
         archetype="corporate", company_type="FZ-LLC", activity="Web3 gaming platform",
         activity_class="PREMIUM (Web3 platform)", risk_tier="MEDIUM-HIGH",
         jurisdiction="RAK DAO", package="Standard office / 8", visa_quota=8,
         premium=True, token_issuing=False, preapproval_status="missing",
         attributes={"parent": {"name": "Immutable Pty Ltd", "reg_country": "Australia",
                                "reg_no": "AU-ACN-162058", "incorp_date": "2018-09-12", "good_standing": True}}),

    # Archetype C — DAO under DARe
    dict(sr="SR-2026-03007", name="Aragon DAO Association", folder="SR-2026-03007_Aragon_DAO_Association__Startup_",
         archetype="dao", company_type="DAO Association (CLG)", activity="DAO governance tooling",
         activity_class="PREMIUM (DAO / DARe)", risk_tier="MEDIUM-HIGH",
         jurisdiction="RAK DARe", package="DAO package / 3", visa_quota=3,
         premium=True, token_issuing=False, preapproval_status="pending",
         attributes={"dao_class": "Startup DAO"}),
    dict(sr="SR-2026-03008", name="Snapshot DAO Association", folder="SR-2026-03008_Snapshot_DAO_Association__Startu",
         archetype="dao", company_type="DAO Association (CLG)", activity="Off-chain governance voting",
         activity_class="PREMIUM (DAO / DARe)", risk_tier="MEDIUM-HIGH",
         jurisdiction="RAK DARe", package="DAO package / 3", visa_quota=3,
         premium=True, token_issuing=False, preapproval_status="pending",
         attributes={"dao_class": "Startup DAO"}),
    dict(sr="SR-2026-03009", name="Tally DAO Association", folder="SR-2026-03009_Tally_DAO_Association__Startup_D",
         archetype="dao", company_type="DAO Association (CLG)", activity="On-chain governance interface",
         activity_class="PREMIUM (DAO / DARe)", risk_tier="MEDIUM-HIGH",
         jurisdiction="RAK DARe", package="DAO package / 3", visa_quota=3,
         premium=True, token_issuing=False, preapproval_status="pending",
         attributes={"dao_class": "Startup DAO"}),
    dict(sr="SR-2026-03010", name="Jupiter Exchange DAO Association", folder="SR-2026-03010_Jupiter_Exchange_DAO_Association",
         archetype="dao", company_type="DAO Association (CLG)", activity="DeFi exchange aggregator",
         activity_class="PREMIUM (DeFi / VASP)", risk_tier="HIGH",
         jurisdiction="RAK DARe", package="DAO package / 4", visa_quota=4,
         premium=True, token_issuing=True, preapproval_status="pending",
         attributes={"dao_class": "Alpha DAO", "vasp_assessment": True}),
    dict(sr="SR-2026-03011", name="Kamino Finance DAO Association", folder="SR-2026-03011_Kamino_Finance_DAO_Association__",
         archetype="dao", company_type="DAO Association (CLG)", activity="DeFi lending protocol",
         activity_class="PREMIUM (DeFi / VASP)", risk_tier="HIGH",
         jurisdiction="RAK DARe", package="DAO package / 4", visa_quota=4,
         premium=True, token_issuing=True, preapproval_status="pending",
         attributes={"dao_class": "Alpha DAO", "vasp_assessment": True}),
]


# Which uploaded (passport, poa) doc pairs describe a person, and that person's role/flags.
def person_specs(archetype: str) -> list[dict]:
    if archetype == "individual":
        return [dict(passport="U01", poa="U02", role="Founder / Shareholder / Director / UBO",
                     is_ubo=True, is_signatory=True, ubo_pct="100%")]
    if archetype == "corporate":
        return [dict(passport="U01", poa="U02", role="Authorised Signatory / Director",
                     is_ubo=False, is_signatory=True, ubo_pct=None)]
    # dao
    return [
        dict(passport="U01", poa="U02", role="Founding Member", is_ubo=True, is_signatory=True, ubo_pct="50%"),
        dict(passport="U03", poa="U04", role="Founding Member", is_ubo=True, is_signatory=True, ubo_pct="50%"),
    ]


def _doc_path(folder: str, doc_key: str) -> Path | None:
    """Find the UPLOADED file whose name starts with the doc_key."""
    updir = DATASET / folder / "UPLOADED"
    if not updir.exists():
        return None
    for f in updir.glob(f"{doc_key}_*.pdf"):
        return f
    return None


def build_person(folder: str, spec: dict) -> dict:
    """Read passport + PoA PDFs into a person row."""
    passport_path = _doc_path(folder, spec["passport"])
    poa_path = _doc_path(folder, spec["poa"])
    pf = extract_fields(passport_path, spec["passport"]) if passport_path else {}
    af = extract_fields(poa_path, spec["poa"]) if poa_path else {}
    return dict(
        name=pf.get("name") or af.get("name") or "Unknown",
        role=spec["role"],
        nationality=pf.get("nationality"),
        dob=to_date(pf.get("dob")),
        pob=pf.get("pob"),
        passport_no=pf.get("passport_no"),
        passport_issue=to_date(pf.get("passport_issue")),
        passport_expiry=to_date(pf.get("passport_expiry")),
        issuing_authority=pf.get("issuing_authority"),
        address=af.get("address"),
        poa_source=af.get("poa_source"),
        poa_date=to_date(af.get("poa_date")),
        ubo_pct=spec["ubo_pct"],
        is_ubo=spec["is_ubo"],
        is_signatory=spec["is_signatory"],
    )


def _index_codes() -> dict[str, set[str]]:
    """SR -> set of doc_key codes present in _INDEX.csv (dataset ground truth)."""
    out: dict[str, set[str]] = {}
    with open(settings.dataset_index, newline="") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["SR"], set()).add(row["Code"])
    return out


def upsert_company(s, c: dict) -> str:
    row = s.execute(text("""
        insert into companies
          (sr, name, archetype, company_type, activity, activity_class, risk_tier, jurisdiction,
           package, visa_quota, premium, token_issuing, preapproval_status, status, attributes)
        values
          (:sr, :name, :archetype, :company_type, :activity, :activity_class, :risk_tier, :jurisdiction,
           :package, :visa_quota, :premium, :token_issuing, :preapproval_status, 'not_started', cast(:attributes as jsonb))
        on conflict (sr) do update set
          name=excluded.name, archetype=excluded.archetype, company_type=excluded.company_type,
          activity=excluded.activity, activity_class=excluded.activity_class, risk_tier=excluded.risk_tier,
          jurisdiction=excluded.jurisdiction, package=excluded.package, visa_quota=excluded.visa_quota,
          premium=excluded.premium, token_issuing=excluded.token_issuing,
          preapproval_status=excluded.preapproval_status, attributes=excluded.attributes
        returning id
    """), dict(**{k: c[k] for k in (
        "sr", "name", "archetype", "company_type", "activity", "activity_class", "risk_tier",
        "jurisdiction", "package", "visa_quota", "premium", "token_issuing", "preapproval_status")},
        attributes=json.dumps(c["attributes"]))).mappings().first()
    return str(row["id"])


def insert_people(s, company_id: str, folder: str, archetype: str) -> int:
    s.execute(text("delete from company_people where company_id = :cid"), dict(cid=company_id))
    n = 0
    for spec in person_specs(archetype):
        p = build_person(folder, spec)
        s.execute(text("""
            insert into company_people
              (company_id, name, role, nationality, dob, pob, passport_no, passport_issue,
               passport_expiry, issuing_authority, address, poa_source, poa_date, ubo_pct, is_ubo, is_signatory)
            values
              (:cid, :name, :role, :nationality, :dob, :pob, :passport_no, :passport_issue,
               :passport_expiry, :issuing_authority, :address, :poa_source, :poa_date, :ubo_pct, :is_ubo, :is_signatory)
        """), dict(cid=company_id, **p))
        n += 1
    return n


def main() -> None:
    index_codes = _index_codes()
    total_people = 0
    with session_scope() as s:
        for c in COMPANIES:
            cid = upsert_company(s, c)
            total_people += insert_people(s, cid, c["folder"], c["archetype"])
            # Sanity check: derived requirements ⊆ dataset codes for this SR.
            model = Company(id=cid, status="not_started", **{k: c[k] for k in (
                "sr", "name", "archetype", "company_type", "activity", "activity_class",
                "risk_tier", "jurisdiction", "package", "visa_quota", "premium",
                "token_issuing", "preapproval_status")}, attributes=c["attributes"])
            derived = {r.doc_key for r in required_documents(model)}
            present = index_codes.get(c["sr"], set())
            missing = derived - present
            flag = "  ⚠ derived-not-in-dataset: " + ",".join(sorted(missing)) if missing else ""
            print(f"  {c['sr']}  {c['name']:<34} {c['archetype']:<11} reqs={len(derived):>2}{flag}")
    print(f"Seeded {len(COMPANIES)} companies, {total_people} people.")


if __name__ == "__main__":
    main()
