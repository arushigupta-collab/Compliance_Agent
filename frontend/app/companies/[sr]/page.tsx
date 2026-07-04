"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { CompanyProfile, getProfile } from "@/lib/api";
import { ArchetypeBadge, PremiumChip, RiskChip, StatusChip } from "@/components/chips";
import { ChecklistPanel } from "@/components/ChecklistPanel";
import { AuditPanel } from "@/components/AuditPanel";

type Tab = "overview" | "audit";

export default function CompanyPage({ params }: { params: Promise<{ sr: string }> }) {
  const { sr } = use(params);
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  const refresh = useCallback(() => getProfile(sr).then(setProfile), [sr]);
  useEffect(() => { refresh(); }, [refresh]);

  if (!profile) return <div className="px-8 py-8 text-sm text-[var(--muted)]">Loading…</div>;
  const c = profile.company;

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview & Documents" },
    { key: "audit", label: "Audit Trail" },
  ];

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-[var(--border)] bg-[var(--surface)] px-8 pt-5">
        <Link href="/" className="mb-3 inline-flex items-center gap-1 text-sm text-[var(--muted)] hover:text-[var(--foreground)]">
          <ArrowLeft size={14} /> Directory
        </Link>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{c.name}</h1>
              <StatusChip status={c.status} />
            </div>
            <div className="mt-1 flex items-center gap-2 text-sm text-[var(--muted)]">
              <span className="font-mono">{c.sr}</span>
              <span>·</span>
              <span>{c.activity}</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <ArchetypeBadge archetype={c.archetype} />
              <RiskChip tier={c.risk_tier} />
              {c.premium && <PremiumChip />}
            </div>
          </div>
          <StartButton profile={profile} />
        </div>

        {/* Tabs */}
        <div className="mt-4 flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`rounded-t-lg px-4 py-2 text-sm transition-colors ${
                tab === t.key
                  ? "border-b-2 border-[var(--accent)] font-medium text-[var(--foreground)]"
                  : "text-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-8 py-6">
        {tab === "overview" && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <EntityFacts profile={profile} />
            <ChecklistPanel profile={profile} onChange={refresh} />
          </div>
        )}
        {tab === "audit" && <AuditPanel sr={sr} />}
      </div>
    </div>
  );
}

function StartButton({ profile }: { profile: CompanyProfile }) {
  // Entry to the compliance flow is the KYC page. It only needs the required
  // documents present; passports get verified on KYC before the run starts.
  const docsMissing = profile.checklist.filter((r) => r.required && r.status !== "extracted");
  const ready = docsMissing.length === 0;
  return (
    <div className="flex flex-col items-end">
      <Link
        href={ready ? `/companies/${profile.company.sr}/kyc` : "#"}
        aria-disabled={!ready}
        title={ready ? "Begin KYC, then run the four-stage pipeline" : `Documents missing: ${docsMissing.map((d) => d.doc_key).join(", ")}`}
        className={`inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-opacity ${
          ready ? "bg-[var(--accent)] text-white hover:opacity-90"
                : "pointer-events-none cursor-not-allowed bg-gray-200 text-gray-400 dark:bg-gray-800 dark:text-gray-600"
        }`}
      >
        Start compliance checks <ArrowRight size={16} />
      </Link>
      {!ready && (
        <div className="mt-2 max-w-xs text-right text-xs text-[var(--muted)]">
          {docsMissing.length} required document(s) missing — load them below first.
        </div>
      )}
    </div>
  );
}

function EntityFacts({ profile }: { profile: CompanyProfile }) {
  const c = profile.company;
  const parent = c.attributes?.parent;
  const facts: [string, string | number | undefined][] = [
    ["Company type", c.company_type],
    ["Activity class", c.activity_class],
    ["Jurisdiction", c.jurisdiction],
    ["Package", c.package],
    ["Visa quota", c.visa_quota],
    ["Token issuing", c.token_issuing ? "Yes" : "No"],
    ["Pre-approval", c.preapproval_status ?? "—"],
  ];
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Entity facts</h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {facts.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2 border-b border-[var(--border)]/60 py-1">
            <dt className="text-[var(--muted)]">{k}</dt>
            <dd className="text-right font-medium">{v}</dd>
          </div>
        ))}
      </dl>
      {parent && (
        <div className="mt-4">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Parent entity</div>
          <div className="rounded-lg bg-[var(--surface)] p-3 text-sm">
            <div className="font-medium">{parent.name}</div>
            <div className="text-xs text-[var(--muted)]">
              {parent.reg_country} · Reg {parent.reg_no} · Incorporated {parent.incorp_date} ·{" "}
              {parent.good_standing ? "Good standing" : "Not in good standing"}
            </div>
          </div>
        </div>
      )}
      <div className="mt-4">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          Parties ({profile.people.length})
        </div>
        <div className="space-y-2">
          {profile.people.map((p) => (
            <div key={p.id} className="flex items-center justify-between rounded-lg bg-[var(--surface)] px-3 py-2 text-sm">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-[var(--muted)]">{p.role}</div>
              </div>
              <div className="text-right text-xs text-[var(--muted)]">
                {p.nationality}
                {p.ubo_pct && <> · UBO {p.ubo_pct}</>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
