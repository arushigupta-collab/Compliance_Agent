"use client";

import { CheckCircle2, CircleDashed, FileCheck2, FileText, Sparkles } from "lucide-react";
import { StageResult } from "@/lib/api";

function KV({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex justify-between border-b border-[var(--border)]/50 py-1">
      <span className="text-[var(--muted)]">{k}</span>
      <span className="font-medium">{v ?? "—"}</span>
    </div>
  );
}

/** Documents reviewed at this stage. */
function StageDocs({ documents }: { documents?: any[] }) {
  if (!documents || documents.length === 0) return null;
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        <FileText size={13} /> Documents reviewed
      </div>
      <div className="divide-y divide-[var(--border)]/60 rounded-lg border border-[var(--border)]">
        {documents.map((d) => {
          const done = d.status === "extracted";
          return (
            <div key={d.doc_key} className="flex items-center gap-3 px-3 py-2 text-sm">
              {done ? <CheckCircle2 size={15} className="text-emerald-500" /> : <CircleDashed size={15} className="text-gray-400" />}
              <span className="w-9 shrink-0 font-mono text-xs text-[var(--muted)]">{d.doc_key}</span>
              <span className="min-w-0 flex-1 truncate">{d.label}</span>
              <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${done ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-gray-100 text-gray-500 dark:bg-gray-800"}`}>
                {done ? "Reviewed" : "Missing"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Insights + reasoning for a stage. */
function Analysis({ analysis }: { analysis?: { reasoning?: string; insights?: string[]; source?: string } }) {
  if (!analysis) return null;
  return (
    <div className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
      <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        <Sparkles size={13} /> Insights &amp; reasoning
      </div>
      {analysis.reasoning && <p className="text-sm">{analysis.reasoning}</p>}
      {analysis.insights && analysis.insights.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm text-[var(--muted)]">
          {analysis.insights.map((s, i) => (
            <li key={i} className="flex gap-2"><span className="text-[var(--accent)]">•</span><span>{s}</span></li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function DvoDetail({ stage }: { stage: StageResult }) {
  const d = stage.detail || {};
  const people = d.person_results || [];
  return (
    <div className="space-y-3">
      {d.narrative && <p className="text-sm italic text-[var(--muted)]">{d.narrative}</p>}
      {people.map((pr: any, i: number) => (
        <div key={i} className={`rounded-lg px-4 py-3 text-sm ${pr.passed ? "bg-emerald-50 dark:bg-emerald-950/40" : "bg-amber-50 dark:bg-amber-950/40"}`}>
          <div className="flex items-center justify-between font-medium">
            <span>{pr.person}</span>
            <span>{pr.passed ? "Verified" : "Flagged"}</span>
          </div>
          <div className="mt-1 grid grid-cols-2 gap-x-6 gap-y-0.5 text-xs text-[var(--muted)]">
            <span>Expiry: {pr.expiry ?? "—"} {pr.expiry_ok ? "✓" : "✗"}</span>
            <span>PoA: {pr.poa_date ?? "—"} {pr.poa_ok ? "✓" : "✗"}</span>
            <span>Face score: {pr.face_match_score ?? "—"} {pr.face_passed ? "✓" : "✗"}</span>
            <span>Role: {pr.role}</span>
          </div>
          {!pr.passed && pr.reasons?.length > 0 && (
            <div className="mt-1 text-xs text-amber-700 dark:text-amber-300">Reasons: {pr.reasons.join(", ")}</div>
          )}
        </div>
      ))}
      {stage.exceptions?.length > 0 && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
          <div className="font-medium">Exceptions flagged to Registry</div>
          {stage.exceptions.map((e: any, i: number) => (
            <div key={i}>· [{e.code}] {e.detail}{e.person ? ` (${e.person})` : ""}{e.doc_key ? ` (${e.doc_key})` : ""}</div>
          ))}
        </div>
      )}
      <StageDocs documents={d.documents} />
      <Analysis analysis={d.analysis} />
    </div>
  );
}

export function ComplianceDetail({ stage }: { stage: StageResult }) {
  const d = stage.detail || {};
  const chain: string[] = d.escalation || [];
  return (
    <div className="space-y-2 text-sm">
      <div><span className="text-[var(--muted)]">Risk tier:</span> <span className="font-medium">{d.tier}</span>
        {stage.risk_score != null && <span className="text-[var(--muted)]"> · score {stage.risk_score}</span>}</div>
      {d.drivers?.length > 0 && (
        <div>
          <div className="text-xs font-medium text-[var(--muted)]">Risk drivers</div>
          <ul className="ml-4 list-disc text-[var(--muted)]">{d.drivers.map((dr: string, i: number) => <li key={i}>{dr}</li>)}</ul>
        </div>
      )}
      <div><span className="text-[var(--muted)]">Pre-approval:</span> <span className="font-medium">{d.preapproval_status ?? "—"}</span></div>
      {chain.length > 0 ? (
        <div>
          <div className="text-xs font-medium text-[var(--muted)]">Escalation chain</div>
          <div className="mt-1 flex items-center gap-2">
            {chain.map((lvl) => (
              <div key={lvl} className="rounded-md bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                {lvl.toUpperCase()} ✓
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-emerald-600 dark:text-emerald-400">Auto-approved at compliance-officer level; no escalation.</div>
      )}
      <StageDocs documents={d.documents} />
      <Analysis analysis={d.analysis} />
    </div>
  );
}

export function LeaseDetail({ stage }: { stage: StageResult }) {
  const d = stage.detail || {};
  return (
    <div>
      <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
        <KV k="Package" v={d.package} />
        <KV k="Term" v={d.term} />
        <KV k="Visa quota" v={d.visa_quota} />
        <KV k="Fee" v={d.fee} />
        <KV k="CRM ref" v={d.crm_ref} />
        <KV k="Status" v="Created" />
      </div>
      <StageDocs documents={d.documents} />
      <Analysis analysis={d.analysis} />
    </div>
  );
}

export function RnlDetail({ stage }: { stage: StageResult }) {
  const d = stage.detail || {};
  if (d.gate === "blocked") {
    return (
      <div>
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
          <div className="font-medium">Blocked at Registry gate</div>
          <div className="mt-0.5">{d.reason}</div>
        </div>
        <StageDocs documents={d.documents} />
        <Analysis analysis={d.analysis} />
      </div>
    );
  }
  return (
    <div className="text-sm">
      <div className="mb-2 flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400">
        <FileCheck2 size={16} /> License Issued · documents visible
      </div>
      <div className="grid grid-cols-2 gap-x-8 gap-y-1">
        <KV k="Certificate" v={d.cert_no} />
        <KV k="License no." v={d.license_no} />
        <KV k="Establishment card" v={d.establishment_card_no} />
      </div>
      {d.outputs && <div className="mt-2 text-xs text-[var(--muted)]">Generated: {d.outputs.join(", ")}</div>}
      <StageDocs documents={d.documents} />
      <Analysis analysis={d.analysis} />
    </div>
  );
}

export function stageStatusOf(stage?: StageResult): string {
  if (!stage) return "todo";
  if (stage.decision === "auto_approved") return "passed";
  return stage.decision;
}
