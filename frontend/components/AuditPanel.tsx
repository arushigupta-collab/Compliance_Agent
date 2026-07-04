"use client";

import { useEffect, useState } from "react";
import { Download, ScrollText } from "lucide-react";
import { AuditEntry, getAudit } from "@/lib/api";

export function AuditPanel({ sr }: { sr: string }) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  useEffect(() => { getAudit(sr).then(setEntries).catch(() => setEntries([])); }, [sr]);

  // Full compliance audit report is generated server-side as a PDF.
  const reportUrl = `/api/v1/companies/${sr}/audit/report`;

  return (
    <section className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          <ScrollText size={16} /> Audit trail
        </h2>
        <a href={reportUrl} target="_blank" rel="noopener noreferrer"
          className={`inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 ${entries.length ? "" : "pointer-events-none opacity-50"}`}>
          <Download size={14} /> Download full audit report (PDF)
        </a>
      </div>

      {entries.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--muted)]">
          No audit entries yet. Actions appear here as you upload, verify, and run the pipeline.
        </div>
      ) : (
        <ol className="relative border-l border-[var(--border)] pl-6">
          {entries.map((e) => (
            <li key={e.id} className="mb-5">
              <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-[var(--accent)]" />
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium capitalize">{e.action.replace(/_/g, " ")}</span>
                <span className="text-xs text-[var(--muted)]">{e.actor}</span>
              </div>
              <div className="text-xs text-[var(--muted)]">{new Date(e.created_at).toLocaleString()}</div>
              {Object.keys(e.payload || {}).length > 0 && (
                <pre className="mt-1 overflow-x-auto rounded-lg bg-[var(--surface)] p-2 text-[11px] text-[var(--muted)]">
                  {JSON.stringify(e.payload)}
                </pre>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
