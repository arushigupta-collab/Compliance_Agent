"use client";

import { useRef, useState } from "react";
import { CheckCircle2, CircleDashed, Download, FileUp, Loader2, Upload } from "lucide-react";
import { ChecklistRow, CompanyProfile, loadSeedDocuments, uploadDocument } from "@/lib/api";

export function ChecklistPanel({ profile, onChange }: { profile: CompanyProfile; onChange: () => void }) {
  const [loading, setLoading] = useState(false);
  const generated = profile.checklist.filter((r) => r.source === "generated");
  const uploaded = profile.checklist.filter((r) => r.source === "uploaded");
  const present = profile.checklist.filter((r) => r.status === "extracted").length;

  const loadAll = async () => {
    setLoading(true);
    try {
      await loadSeedDocuments(profile.company.sr);
      await onChange();
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Document checklist</h2>
          <div className="mt-0.5 text-xs text-[var(--muted)]">
            {present}/{profile.checklist.length} extracted
          </div>
        </div>
        <button
          onClick={loadAll}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--foreground)] px-3 py-1.5 text-xs font-medium text-[var(--background)] hover:opacity-90 disabled:opacity-50"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          Load portal + customer documents
        </button>
      </div>

      <Group title="Portal-generated" rows={generated} sr={profile.company.sr} onChange={onChange} />
      <div className="mt-4">
        <Group title="Customer-uploaded" rows={uploaded} sr={profile.company.sr} onChange={onChange} />
      </div>
    </section>
  );
}

function Group({ title, rows, sr, onChange }: { title: string; rows: ChecklistRow[]; sr: string; onChange: () => void }) {
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{title}</div>
      <div className="divide-y divide-[var(--border)]/60 rounded-lg border border-[var(--border)]">
        {rows.map((r) => <Row key={r.doc_key} row={r} sr={sr} onChange={onChange} />)}
      </div>
    </div>
  );
}

function Row({ row, sr, onChange }: { row: ChecklistRow; sr: string; onChange: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const done = row.status === "extracted";

  const onFile = async (f: File) => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("doc_key", row.doc_key);
      fd.append("source", row.source);
      fd.append("file", f);
      await uploadDocument(sr, fd);
      await onChange();
    } finally {
      setBusy(false);
    }
  };

  const peek = Object.entries(row.extracted_fields || {})
    .filter(([k]) => !k.startsWith("_"))
    .slice(0, 3)
    .map(([k, v]) => `${k}: ${v}`)
    .join(" · ");

  return (
    <div className="flex items-center gap-3 px-3 py-2.5 text-sm">
      <span className="shrink-0">
        {done ? <CheckCircle2 size={16} className="text-emerald-500" /> : <CircleDashed size={16} className="text-gray-400" />}
      </span>
      <span className="w-10 shrink-0 font-mono text-xs text-[var(--muted)]">{row.doc_key}</span>
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium">{row.label}</div>
        {done && peek && <div className="truncate text-xs text-[var(--muted)]">{peek}</div>}
      </div>
      <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${done ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-gray-100 text-gray-500 dark:bg-gray-800"}`}>
        {done ? "Extracted" : "Missing"}
      </span>
      <button onClick={() => fileRef.current?.click()} disabled={busy}
        className="shrink-0 rounded p-1 text-[var(--muted)] hover:bg-[var(--surface)] hover:text-[var(--foreground)]">
        {busy ? <Loader2 size={14} className="animate-spin" /> : done ? <FileUp size={14} /> : <Upload size={14} />}
      </button>
      <input ref={fileRef} type="file" accept="application/pdf,image/*" className="hidden"
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
    </div>
  );
}
