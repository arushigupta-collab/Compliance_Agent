"""Lazy per-stage streaming runner (UI).

A stage's check runs only when its page is reached (the SSE stream connects),
and its content is emitted bit by bit: documents, then the decision/detail,
then escalations (with delays), then the analysis reasoning word-by-word and
insights one-by-one. Prerequisite stages are computed silently if missing; if a
prerequisite ended the process, the requested stage reports "not reached".
"""
from __future__ import annotations

import time
from typing import Iterator

from app.config import settings
from app.pipeline import nodes
from app.pipeline.graph import _analysis_for, build_context

_TERMINAL_DECISIONS = {"flagged", "blocked"}


def _reason_from_outcome(out) -> str:
    if out.decision == "blocked":
        return (out.detail or {}).get("reason", "blocked at Registry & Licensing")
    if out.decision == "flagged":
        ex = out.exceptions or []
        return "; ".join(f"{e.get('code')} ({e.get('person', e.get('doc_key', ''))})" for e in ex[:3]) or "flagged at DVO"
    return "all stages cleared"


def _next_stage(stage: str, terminal: bool) -> str | None:
    if terminal:
        return None
    i = nodes.ORDER.index(stage)
    return nodes.ORDER[i + 1] if i + 1 < len(nodes.ORDER) else None


def _stream_analysis(analysis: dict) -> Iterator[dict]:
    yield {"type": "analysis_start", "source": analysis.get("source", "rules")}
    words = (analysis.get("reasoning") or "").split()
    buf: list[str] = []
    for w in words:
        buf.append(w)
        if len(buf) >= 3:
            yield {"type": "analysis_chunk", "text": " ".join(buf) + " "}
            buf = []
            time.sleep(0.04)
    if buf:
        yield {"type": "analysis_chunk", "text": " ".join(buf)}
    for ins in analysis.get("insights") or []:
        time.sleep(0.12)
        yield {"type": "insight", "text": ins}


def _persist_escalations_stream(repo, run_id: str, chain: list[str]) -> Iterator[dict]:
    for level in chain:
        repo.create_escalation(run_id, level)
    for level in chain:
        time.sleep(0.6 if settings.auto_escalate else 0.0)
        repo.set_escalation(run_id, level, "approved", "auto-demo")
        yield {"type": "escalation", "level": level, "status": "approved"}


def stream_stage(repo, run_id: str, company_id: str, stage: str) -> Iterator[dict]:
    if stage not in nodes.ORDER:
        yield {"type": "error", "message": f"unknown stage {stage}"}
        return

    ctx = build_context(repo, run_id, company_id)
    company = ctx["company"]
    run = repo.get_run(run_id)
    executed = {s.stage: s for s in (run.stages if run else [])}
    idx = nodes.ORDER.index(stage)

    # Ensure prerequisites are computed (silently). If one ended the process,
    # the requested stage was never reached.
    for pre in nodes.ORDER[:idx]:
        if pre in executed:
            if executed[pre].decision in _TERMINAL_DECISIONS:
                yield {"type": "not_reached", "endedAt": pre, "endedDecision": executed[pre].decision}
                return
            continue
        out = nodes.compute_stage(pre, ctx)
        analysis = _analysis_for(out, company.name)
        if out.escalation_chain:
            for lvl in out.escalation_chain:
                repo.create_escalation(run_id, lvl)
                repo.set_escalation(run_id, lvl, "approved", "auto-demo")
        nodes.persist_outcome(repo, run_id, company_id, out, analysis)
        if out.terminal:
            repo.finish_run(run_id, out.final_status or "flagged", {"final_status": out.final_status})
            nodes.record_verification(repo, company, run_id, out.final_status or "flagged",
                                      _reason_from_outcome(out))
            yield {"type": "not_reached", "endedAt": pre, "endedDecision": out.decision}
            return

    # Replay an already-computed stage (still streamed for a consistent feel).
    if stage in executed:
        st = executed[stage]
        detail = st.detail or {}
        terminal = stage == "rnl" or st.decision in _TERMINAL_DECISIONS
        yield {"type": "stage_start", "stage": stage, "replay": True}
        yield {"type": "documents", "documents": detail.get("documents", [])}
        yield {"type": "decision", "stage": stage, "decision": st.decision,
               "risk_score": st.risk_score, "detail": {k: v for k, v in detail.items() if k != "analysis"}}
        for lvl in detail.get("escalation", []) or []:
            yield {"type": "escalation", "level": lvl, "status": "approved"}
        yield from _stream_analysis(detail.get("analysis") or {})
        yield {"type": "stage_done", "decision": st.decision, "terminal": terminal,
               "final_status": run.status if run else None, "next": _next_stage(stage, terminal)}
        return

    # Compute + stream the requested stage now.
    out = nodes.compute_stage(stage, ctx)
    yield {"type": "stage_start", "stage": stage}
    yield {"type": "documents", "documents": out.detail.get("documents", [])}
    time.sleep(0.15)
    yield {"type": "decision", "stage": stage, "decision": out.decision,
           "risk_score": out.risk_score, "detail": out.detail}

    if out.escalation_chain:
        yield from _persist_escalations_stream(repo, run_id, out.escalation_chain)

    analysis = _analysis_for(out, company.name)
    yield from _stream_analysis(analysis)

    nodes.persist_outcome(repo, run_id, company_id, out, analysis)
    if out.terminal:
        repo.finish_run(run_id, out.final_status or "flagged", {"final_status": out.final_status})
        nodes.record_verification(repo, company, run_id, out.final_status or "flagged",
                                  _reason_from_outcome(out))

    yield {"type": "stage_done", "decision": out.decision, "terminal": out.terminal,
           "final_status": out.final_status, "next": _next_stage(stage, out.terminal)}
