"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, CircleDashed, Loader2, XCircle, AlertTriangle, GitBranch, FileCheck2 } from "lucide-react";
import { LeaseRecord, License, RunSummary, getLease, getLicense, getRun, runStreamUrl } from "@/lib/api";

const STAGES = [
  { key: "dvo", label: "DVO — Document Verification" },
  { key: "compliance", label: "Compliance & Risk" },
  { key: "lease", label: "Lease (CRM)" },
  { key: "rnl", label: "Registry & Licensing" },
];

interface StageState {
  decision?: string;
  detail?: any;
  exceptions?: any[];
  running?: boolean;
}

export function RunPanel({ sr, runId, onFinished }: { sr: string; runId: string | null; onFinished: () => void }) {
  const [stages, setStages] = useState<Record<string, StageState>>({});
  const [log, setLog] = useState<string[]>([]);
  const [escalations, setEscalations] = useState<{ level: string; status: string }[]>([]);
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [lease, setLease] = useState<LeaseRecord | null>(null);
  const [license, setLicense] = useState<License | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;
    setStages({}); setLog([]); setEscalations([]); setFinalStatus(null); setLease(null); setLicense(null);

    const es = new EventSource(runStreamUrl(runId));
    esRef.current = es;
    es.onmessage = (e) => {
      let ev: any;
      try { ev = JSON.parse(e.data); } catch { return; }
      const t = ev.type;
      if (t === "stage_start") {
        setStages((s) => ({ ...s, [ev.stage]: { ...s[ev.stage], running: true } }));
        setLog((l) => [...l, `▶ ${ev.stage.toUpperCase()} started`]);
      } else if (t === "stage_result") {
        setStages((s) => ({ ...s, [ev.stage]: { decision: ev.decision, detail: ev.detail, exceptions: ev.exceptions, running: false } }));
        setLog((l) => [...l, `● ${ev.stage.toUpperCase()} → ${ev.decision}`]);
      } else if (t === "escalation") {
        setEscalations((x) => [...x, { level: ev.level, status: ev.status }]);
        setLog((l) => [...l, `⇧ Escalation ${ev.level} → ${ev.status}`]);
      } else if (t === "run_complete") {
        setFinalStatus(ev.status);
        setLog((l) => [...l, `✔ Run complete → ${ev.status}`]);
        es.close();
        getLease(sr).then(setLease).catch(() => {});
        getLicense(sr).then(setLicense).catch(() => {});
        onFinished();
      }
    };
    es.onerror = () => { es.close(); };
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  if (!runId) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--muted)]">
        No active run. Use <span className="font-medium">Run compliance checks</span> to start the pipeline.
      </div>
    );
  }

  const stageStatus = (key: string): "idle" | "running" | "passed" | "flagged" | "blocked" | "escalated" => {
    const s = stages[key];
    if (!s) return "idle";
    if (s.running) return "running";
    if (s.decision === "flagged") return "flagged";
    if (s.decision === "blocked") return "blocked";
    if (s.decision === "escalated") return "escalated";
    return "passed";
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* Stepper + details */}
      <div className="space-y-4 lg:col-span-2">
        {STAGES.map((st) => (
          <StageCard key={st.key} label={st.label} status={stageStatus(st.key)} state={stages[st.key]}
            escalations={st.key === "compliance" ? escalations : undefined}
            lease={st.key === "lease" ? lease : undefined}
            license={st.key === "rnl" ? license : undefined} />
        ))}
        {finalStatus && <FinalBanner status={finalStatus} />}
      </div>

      {/* Event log */}
      <div>
        <div className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Live event log</div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 font-mono text-xs">
          {log.length === 0 ? <div className="text-[var(--muted)]">Waiting…</div> :
            log.map((l, i) => <div key={i} className="py-0.5">{l}</div>)}
        </div>
      </div>
    </div>
  );
}

function StageIcon({ status }: { status: string }) {
  if (status === "running") return <Loader2 size={18} className="animate-spin text-blue-500" />;
  if (status === "passed") return <CheckCircle2 size={18} className="text-emerald-500" />;
  if (status === "flagged") return <AlertTriangle size={18} className="text-amber-500" />;
  if (status === "blocked") return <XCircle size={18} className="text-red-500" />;
  if (status === "escalated") return <GitBranch size={18} className="text-orange-500" />;
  return <CircleDashed size={18} className="text-gray-300 dark:text-gray-700" />;
}

function StageCard({ label, status, state, escalations, lease, license }: {
  label: string; status: string; state?: StageState;
  escalations?: { level: string; status: string }[]; lease?: LeaseRecord | null; license?: License | null;
}) {
  const d = state?.detail;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-4">
      <div className="flex items-center gap-3">
        <StageIcon status={status} />
        <div className="flex-1">
          <div className="font-medium">{label}</div>
          {state?.decision && <div className="text-xs capitalize text-[var(--muted)]">{state.decision.replace("_", " ")}</div>}
        </div>
      </div>

      {/* DVO detail */}
      {d?.person_results && (
        <div className="mt-3 space-y-2">
          {d.person_results.map((pr: any, i: number) => (
            <div key={i} className={`rounded-lg px-3 py-2 text-xs ${pr.passed ? "bg-emerald-50 dark:bg-emerald-950/40" : "bg-amber-50 dark:bg-amber-950/40"}`}>
              <div className="flex justify-between font-medium">
                <span>{pr.person}</span>
                <span>{pr.passed ? "Verified" : "Flagged"}</span>
              </div>
              {!pr.passed && <div className="mt-0.5 text-amber-700 dark:text-amber-300">Reasons: {pr.reasons.join(", ")}</div>}
            </div>
          ))}
          {state?.exceptions && state.exceptions.length > 0 && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
              <div className="font-medium">Flagged to Registry</div>
              {state.exceptions.map((e: any, i: number) => (
                <div key={i}>· [{e.code}] {e.detail}{e.person ? ` (${e.person})` : ""}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Compliance detail */}
      {d?.tier && (
        <div className="mt-3 text-xs">
          <div className="mb-1"><span className="text-[var(--muted)]">Risk tier:</span> <span className="font-medium">{d.tier}</span></div>
          {d.drivers && <ul className="ml-4 list-disc text-[var(--muted)]">{d.drivers.map((dr: string, i: number) => <li key={i}>{dr}</li>)}</ul>}
          {d.preapproval_status !== undefined && (
            <div className="mt-1"><span className="text-[var(--muted)]">Pre-approval:</span> <span className="font-medium">{d.preapproval_status ?? "—"}</span></div>
          )}
          {(escalations && escalations.length > 0) || (d.escalation && d.escalation.length > 0) ? (
            <div className="mt-2 flex items-center gap-2">
              {(d.escalation || []).map((lvl: string) => {
                const done = escalations?.find((e) => e.level === lvl);
                return (
                  <div key={lvl} className={`rounded-md px-2 py-1 text-[10px] font-medium ${done ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-gray-100 text-gray-500 dark:bg-gray-800"}`}>
                    {lvl.toUpperCase()} {done ? "✓" : "…"}
                  </div>
                );
              })}
            </div>
          ) : d.escalation && d.escalation.length === 0 ? (
            <div className="mt-1 text-emerald-600 dark:text-emerald-400">Auto-approved at compliance-officer level.</div>
          ) : null}
          {d.narrative && <p className="mt-2 italic text-[var(--muted)]">{d.narrative}</p>}
        </div>
      )}

      {/* Lease detail */}
      {lease && (
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <KV k="Package" v={lease.package} /><KV k="Term" v={lease.term} />
          <KV k="Visa quota" v={lease.visa_quota} /><KV k="Fee" v={lease.fee} />
          <KV k="CRM ref" v={lease.crm_ref} /><KV k="Status" v={lease.status} />
        </div>
      )}

      {/* R&L / issuance */}
      {d?.gate === "blocked" && (
        <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
          <div className="font-medium">Blocked at Registry gate</div>
          <div>{d.reason}</div>
          {d.narrative && <p className="mt-1 italic">{d.narrative}</p>}
        </div>
      )}
      {license && d?.gate === "passed" && (
        <div className="mt-3 text-xs">
          <div className="mb-2 flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400">
            <FileCheck2 size={14} /> License Issued · documents visible
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <KV k="Certificate" v={license.cert_no} /><KV k="License no." v={license.license_no} />
            <KV k="Establishment" v={license.establishment_card_no} />
          </div>
          {d.outputs && <div className="mt-2 text-[var(--muted)]">Generated: {d.outputs.join(", ")}</div>}
        </div>
      )}
    </div>
  );
}

function KV({ k, v }: { k: string; v: any }) {
  return <div className="flex justify-between border-b border-[var(--border)]/50 py-0.5"><span className="text-[var(--muted)]">{k}</span><span className="font-medium">{v ?? "—"}</span></div>;
}

function FinalBanner({ status }: { status: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    license_issued: { cls: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300", label: "License Issued" },
    flagged: { cls: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300", label: "Flagged at DVO — routed back to Registry" },
    blocked: { cls: "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300", label: "Blocked at Registry & Licensing" },
  };
  const m = map[status] ?? { cls: "border-[var(--border)]", label: status };
  return <div className={`rounded-xl border px-4 py-3 text-sm font-medium ${m.cls}`}>{m.label}</div>;
}
