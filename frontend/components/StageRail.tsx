"use client";

import Link from "next/link";
import { AlertTriangle, Check, CircleDashed, GitBranch, Loader2, Minus, XCircle } from "lucide-react";

export const RAIL_STEPS = [
  { key: "kyc", label: "KYC" },
  { key: "dvo", label: "DVO" },
  { key: "compliance", label: "Compliance & Risk" },
  { key: "lease", label: "Lease" },
  { key: "rnl", label: "Registry & Licensing" },
] as const;

export type StepKey = (typeof RAIL_STEPS)[number]["key"];

// status per step: done|passed|flagged|blocked|escalated|running|current|todo|skipped
export interface RailState {
  current: StepKey;
  status: Partial<Record<StepKey, string>>;
  // href builder for a step (null = not navigable)
  hrefFor: (k: StepKey) => string | null;
}

function icon(status: string | undefined, isCurrent: boolean) {
  switch (status) {
    case "passed":
    case "done":
    case "auto_approved":
      return <Check size={13} />;
    case "flagged":
      return <AlertTriangle size={13} />;
    case "blocked":
      return <XCircle size={13} />;
    case "escalated":
      return <GitBranch size={13} />;
    case "running":
      return <Loader2 size={13} className="animate-spin" />;
    case "skipped":
      return <Minus size={13} />;
    default:
      return isCurrent ? <CircleDashed size={13} /> : <CircleDashed size={13} className="opacity-40" />;
  }
}

function tone(status: string | undefined, isCurrent: boolean): string {
  if (isCurrent) return "border-[var(--accent)] bg-[var(--accent)] text-white";
  switch (status) {
    case "passed":
    case "done":
    case "auto_approved":
      return "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300";
    case "flagged":
      return "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300";
    case "blocked":
      return "border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300";
    case "escalated":
      return "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-300";
    case "running":
      return "border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300";
    case "skipped":
      return "border-[var(--border)] text-[var(--muted)] opacity-60";
    default:
      return "border-[var(--border)] text-[var(--muted)]";
  }
}

export function StageRail({ state }: { state: RailState }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {RAIL_STEPS.map((step, i) => {
        const isCurrent = step.key === state.current;
        const st = state.status[step.key];
        const href = state.hrefFor(step.key);
        const chip = (
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${tone(st, isCurrent)} ${href && !isCurrent ? "hover:opacity-80" : ""}`}>
            {icon(st, isCurrent)} {step.label}
          </span>
        );
        return (
          <span key={step.key} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-[var(--border)]">→</span>}
            {href && !isCurrent ? <Link href={href}>{chip}</Link> : chip}
          </span>
        );
      })}
    </div>
  );
}
