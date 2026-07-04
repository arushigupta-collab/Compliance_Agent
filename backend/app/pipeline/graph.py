"""Batch pipeline runner (used by the Section 9 oracle) + shared context.

The UI uses the lazy per-stage streaming runner (stage_runner.py); this batch
runner executes every stage in order in one call, for headless verification.
Both share the pure compute functions in nodes.py.
"""
from __future__ import annotations

from typing import Any

from app.llm import stage_analysis
from app.pipeline import nodes
from app.pipeline.events import bus


def build_context(repo, run_id: str, company_id: str) -> dict[str, Any]:
    """Assemble everything the stages need, including stage->documents."""
    from app.rules.checklist import stage_documents

    from app.config import settings

    company = repo.get_company_by_id(company_id)
    people = repo.get_people(company_id)
    pvs = repo.get_passport_verifications(company_id)
    docs = repo.get_document_status(company_id)
    if settings.data_source == "supabase":
        from app.supabase_map import stage_documents_supabase
        stage_docs = stage_documents_supabase(docs)
    else:
        stage_docs = stage_documents(company, {d.doc_key: d for d in docs})
    return {"company": company, "people": people, "pvs": pvs, "docs": docs,
            "stage_docs": stage_docs, "run_id": run_id}


def _analysis_for(outcome: nodes.StageOutcome, company_name: str) -> dict:
    return stage_analysis(
        stage=nodes.STAGE_TITLES.get(outcome.stage, outcome.stage), company_name=company_name,
        facts=outcome.analysis_facts, fallback_reasoning=outcome.fallback_reasoning,
        fallback_insights=outcome.fallback_insights)


def run_pipeline(repo, run_id: str, company_id: str) -> dict:
    """Execute all stages in order (batch). Persists stage rows + escalations."""
    ctx = build_context(repo, run_id, company_id)
    company = ctx["company"]
    bus.emit(run_id, {"type": "run_start", "company": company.sr})
    repo.audit(company_id=company_id, run_id=run_id, actor="pipeline", action="run_started", payload={})

    final_status = "license_issued"
    for stage in nodes.ORDER:
        outcome = nodes.compute_stage(stage, ctx)
        analysis = _analysis_for(outcome, company.name)
        if outcome.escalation_chain:
            for level in outcome.escalation_chain:
                repo.create_escalation(run_id, level)
                repo.set_escalation(run_id, level, "approved", "auto-demo")
        nodes.persist_outcome(repo, run_id, company_id, outcome, analysis)
        bus.emit(run_id, {"type": "stage_result", "stage": stage, "decision": outcome.decision})
        if outcome.terminal:
            final_status = outcome.final_status or "flagged"
            break

    repo.finish_run(run_id, final_status, {"final_status": final_status})
    nodes.record_verification(repo, company, run_id, final_status, terminal_reason(repo, run_id))
    bus.emit(run_id, {"type": "run_complete", "status": final_status})
    return {"run_id": run_id, "status": final_status}


def terminal_reason(repo, run_id: str) -> str:
    """Human-readable reason from the last stage's decision/exception detail."""
    run = repo.get_run(run_id)
    if not run or not run.stages:
        return ""
    last = run.stages[-1]
    if last.decision == "blocked":
        return (last.detail or {}).get("reason", "blocked at Registry & Licensing")
    if last.decision == "flagged":
        ex = last.exceptions or []
        return "; ".join(f"{e.get('code')} ({e.get('person', e.get('doc_key', ''))})" for e in ex[:3]) or "flagged at DVO"
    return "all stages cleared"
