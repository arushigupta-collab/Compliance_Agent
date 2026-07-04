"""Risk scoring + escalation chain per spec §7.4.

Deterministic and auditable: the tier comes from seeded facts; the escalation
chain follows from the tier. The LLM (compliance node) adds narrative only.
"""
from __future__ import annotations

from typing import Any

from app.domain.models import Company, Person
from app.rules.checklist import is_premium

# Tiers that require the full officer -> senior -> director chain.
_ESCALATE_TIERS = {"MEDIUM-HIGH", "HIGH"}


def _tier(company: Company) -> str:
    return company.risk_tier.strip().upper()


def score(company: Company, people: list[Person], screenings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return {tier, drivers[]} for the compliance node."""
    screenings = screenings or {}
    drivers: list[str] = []

    drivers.append(f"Activity classification: {company.activity_class}")
    if company.jurisdiction:
        drivers.append(f"Jurisdiction: {company.jurisdiction}")

    if company.archetype == "corporate":
        parent = (company.attributes or {}).get("parent", {})
        pname = parent.get("name") if isinstance(parent, dict) else None
        drivers.append(f"Multi-layer ownership (parent: {pname or 'corporate parent'})")
    if company.archetype == "dao":
        drivers.append("DAO governance structure under DARe")

    if is_premium(company):
        drivers.append("Premium activity flag")
    if company.token_issuing:
        drivers.append("Token issuance / VASP assessment")

    ubos = [p for p in people if p.is_ubo]
    if len(ubos) > 1:
        drivers.append(f"Multiple UBOs ({len(ubos)})")

    if screenings.get("pep_hits"):
        drivers.append(f"PEP screening hits: {screenings['pep_hits']}")
    if screenings.get("sanctions_hits"):
        drivers.append(f"Sanctions screening hits: {screenings['sanctions_hits']}")

    return {"tier": _tier(company), "drivers": drivers}


def escalation_chain(tier: str) -> list[str]:
    """Low/medium -> auto-approve ([]); medium-high/high -> full chain."""
    if tier.strip().upper() in _ESCALATE_TIERS:
        return ["officer", "senior", "director"]
    return []
