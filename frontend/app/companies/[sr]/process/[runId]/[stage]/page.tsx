"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Loader2 } from "lucide-react";
import { RunSummary, StageResult, getRun, stageStreamUrl } from "@/lib/api";
import { RAIL_STEPS, StageRail, StepKey } from "@/components/StageRail";
import { ComplianceDetail, DvoDetail, LeaseDetail, RnlDetail, stageStatusOf } from "@/components/stageDetails";
import { StatusChip } from "@/components/chips";

const PIPELINE: StepKey[] = ["dvo", "compliance", "lease", "rnl"];
const TITLES: Record<string, string> = {
  dvo: "DVO — Document Verification",
  compliance: "Compliance & Risk",
  lease: "Lease (CRM)",
  rnl: "Registry & Licensing",
};

interface LiveState {
  phase: "connecting" | "running" | "done" | "not_reached";
  decision?: string;
  detail: any;                 // accumulates documents, decision detail, analysis
  escalations: string[];
  next?: string | null;
  terminal?: boolean;
  endedAt?: string;
  endedDecision?: string;
}

export default function StagePage({ params }: { params: Promise<{ sr: string; runId: string; stage: string }> }) {
  const { sr, runId, stage } = use(params);
  const [live, setLive] = useState<LiveState>({ phase: "connecting", detail: {}, escalations: [] });
  const [run, setRun] = useState<RunSummary | null>(null);
  const esRef = useRef<EventSource | null>(null);

  // Fetch run for the rail (statuses of other stages). Refetched on stage_done.
  const loadRun = () => getRun(runId).then(setRun).catch(() => {});

  useEffect(() => {
    setLive({ phase: "connecting", detail: {}, escalations: [] });
    loadRun();
    const es = new EventSource(stageStreamUrl(runId, stage));
    esRef.current = es;
    es.onmessage = (e) => {
      let ev: any;
      try { ev = JSON.parse(e.data); } catch { return; }
      switch (ev.type) {
        case "stage_start":
          setLive((s) => ({ ...s, phase: "running" }));
          break;
        case "documents":
          setLive((s) => ({ ...s, detail: { ...s.detail, documents: ev.documents } }));
          break;
        case "decision":
          setLive((s) => ({ ...s, decision: ev.decision,
            detail: { ...s.detail, ...ev.detail, risk_score: ev.risk_score } }));
          break;
        case "escalation":
          setLive((s) => ({ ...s, escalations: [...s.escalations, ev.level] }));
          break;
        case "analysis_start":
          setLive((s) => ({ ...s, detail: { ...s.detail, analysis: { reasoning: "", insights: [], source: ev.source } } }));
          break;
        case "analysis_chunk":
          setLive((s) => ({ ...s, detail: { ...s.detail, analysis: { ...s.detail.analysis,
            reasoning: (s.detail.analysis?.reasoning || "") + ev.text } } }));
          break;
        case "insight":
          setLive((s) => ({ ...s, detail: { ...s.detail, analysis: { ...s.detail.analysis,
            insights: [...(s.detail.analysis?.insights || []), ev.text] } } }));
          break;
        case "stage_done":
          setLive((s) => ({ ...s, phase: "done", decision: ev.decision, terminal: ev.terminal, next: ev.next }));
          es.close();
          loadRun();
          break;
        case "not_reached":
          setLive((s) => ({ ...s, phase: "not_reached", endedAt: ev.endedAt, endedDecision: ev.endedDecision }));
          es.close();
          loadRun();
          break;
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, stage]);

  // Rail status: executed stages from run, current from live, others todo/skipped.
  const executed: Record<string, StageResult> = {};
  run?.stages.forEach((s) => { executed[s.stage] = s; });
  const status: Partial<Record<StepKey, string>> = { kyc: "done" };
  PIPELINE.forEach((k) => {
    if (k === stage) status[k] = live.phase === "done" ? stageStatusOf({ decision: live.decision } as any)
      : live.phase === "not_reached" ? "skipped" : "running";
    else if (executed[k]) status[k] = stageStatusOf(executed[k]);
    else status[k] = "todo";
  });
  const hrefFor = (k: StepKey): string | null => {
    if (k === stage) return null;
    if (k === "kyc") return `/companies/${sr}/kyc`;
    return `/companies/${sr}/process/${runId}/${k}`;  // navigable; target runs lazily
  };

  const liveResult: StageResult = {
    stage, decision: live.decision || "", exceptions: live.detail.exceptions || [],
    risk_score: live.detail.risk_score, detail: live.detail,
  };

  const nextHref = live.next ? `/companies/${sr}/process/${runId}/${live.next}` : null;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-[var(--border)] bg-[var(--surface)] px-8 pb-5 pt-5">
        <Link href={`/companies/${sr}`} className="mb-3 inline-flex items-center gap-1 text-sm text-[var(--muted)] hover:text-[var(--foreground)]">
          <ArrowLeft size={14} /> Back to profile
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{TITLES[stage] ?? stage}</h1>
            {run && <StatusChip status={run.status} />}
            {live.phase === "running" && <Loader2 size={16} className="animate-spin text-blue-500" />}
          </div>
          <span className="font-mono text-xs text-[var(--muted)]">run {runId.slice(0, 8)}</span>
        </div>
        <div className="mt-4">
          <StageRail state={{ current: stage as StepKey, status, hrefFor }} />
        </div>
      </div>

      <div className="flex-1 overflow-auto px-8 py-6">
        <div className="mx-auto max-w-3xl">
          {live.phase === "not_reached" ? (
            <div className="rounded-xl border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--muted)]">
              This stage was not reached — the process ended earlier at{" "}
              <span className="font-medium">{live.endedAt?.toUpperCase()}</span> ({live.endedDecision}).
            </div>
          ) : live.phase === "connecting" ? (
            <div className="flex items-center gap-2 rounded-xl border border-[var(--border)] p-8 text-sm text-[var(--muted)]">
              <Loader2 size={16} className="animate-spin" /> Starting {TITLES[stage]?.split(" ")[0]} check…
            </div>
          ) : (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-5">
              <StageBody stage={stage} result={liveResult} escalations={live.escalations} />
            </div>
          )}

          <div className="mt-6 flex items-center justify-between">
            <Link href={`/companies/${sr}/kyc`} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-4 py-2 text-sm hover:bg-[var(--surface)]">
              <ArrowLeft size={14} /> KYC
            </Link>
            {live.phase === "done" && nextHref && (
              <Link href={nextHref} className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90">
                Next: {TITLES[live.next as string]?.split(" ")[0]} <ArrowRight size={14} />
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StageBody({ stage, result, escalations }: { stage: string; result: StageResult; escalations: string[] }) {
  // For a live compliance run, reflect streamed escalation approvals.
  if (stage === "compliance" && escalations.length && result.detail) {
    result = { ...result, detail: { ...result.detail, _live_escalations: escalations } };
  }
  return (
    <>
      {stage === "dvo" && <DvoDetail stage={result} />}
      {stage === "compliance" && <ComplianceDetail stage={result} />}
      {stage === "lease" && <LeaseDetail stage={result} />}
      {stage === "rnl" && <RnlDetail stage={result} />}
    </>
  );
}
