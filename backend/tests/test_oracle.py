"""Section 9 acceptance oracle: all 15 companies must reproduce their end state.

Runs the pipeline headless (directly, no HTTP) for each seeded company and
asserts the final company status + the stage at which it stopped.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.deps import get_repository
from app.pipeline.graph import run_pipeline

# sr -> (expected final status, expected terminal stage)
ORACLE = {
    "SR-2026-01042": ("license_issued", "rnl"),
    "SR-2026-01043": ("license_issued", "rnl"),
    "SR-2026-01044": ("license_issued", "rnl"),
    "SR-2026-01045": ("license_issued", "rnl"),
    "SR-2026-01046": ("license_issued", "rnl"),
    "SR-2026-02012": ("license_issued", "rnl"),
    "SR-2026-02013": ("license_issued", "rnl"),
    "SR-2026-02011": ("flagged", "dvo"),
    "SR-2026-03010": ("flagged", "dvo"),
    "SR-2026-02014": ("blocked", "rnl"),
    "SR-2026-02015": ("blocked", "rnl"),
    "SR-2026-03007": ("blocked", "rnl"),
    "SR-2026-03008": ("blocked", "rnl"),
    "SR-2026-03009": ("blocked", "rnl"),
    "SR-2026-03011": ("blocked", "rnl"),
}


@pytest.mark.parametrize("sr,expected", ORACLE.items())
def test_company_end_state(sr, expected):
    exp_status, exp_stage = expected
    repo = get_repository()
    company = repo.get_company(sr)
    assert company, f"{sr} not seeded"

    repo.set_company_status(company.id, "not_started")
    # DVO now strictly depends on KYC — seed a deterministic KYC verification per
    # person (mirrors what the KYC screen does in the UI) before running headless.
    from app.services import ensure_kyc
    for person in repo.get_people(company.id):
        ensure_kyc(repo, company.id, person)
    run_id = repo.create_run(company.id)
    result = run_pipeline(repo, run_id, company.id)

    assert result["status"] == exp_status, f"{sr}: got {result['status']}, want {exp_status}"

    run = repo.get_run(run_id)
    last_stage = run.stages[-1].stage if run.stages else None
    assert last_stage == exp_stage, f"{sr}: stopped at {last_stage}, want {exp_stage}"

    final = repo.get_company(sr)
    assert final.status == exp_status
