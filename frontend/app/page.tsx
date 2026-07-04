"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Search } from "lucide-react";
import { Company, SchemaHealth, getCompanies, getSchemaHealth } from "@/lib/api";
import { ArchetypeBadge, PremiumChip, RiskChip, StatusChip } from "@/components/chips";

export default function DirectoryPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [health, setHealth] = useState<SchemaHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [archetype, setArchetype] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    getCompanies().then(setCompanies).finally(() => setLoading(false));
    getSchemaHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  const filtered = useMemo(
    () =>
      companies.filter(
        (c) =>
          (!q || c.name.toLowerCase().includes(q.toLowerCase()) || c.sr.toLowerCase().includes(q.toLowerCase())) &&
          (!archetype || c.archetype === archetype) &&
          (!status || c.status === status)
      ),
    [companies, q, archetype, status]
  );

  return (
    <div className="mx-auto max-w-7xl px-8 py-8">
      <div className="mb-1 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Company Directory</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            15 seeded companies across three archetypes. Open a profile to upload documents and run the compliance pipeline.
          </p>
        </div>
      </div>

      {health && !health.ok && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
          <AlertTriangle size={16} className="mt-0.5" />
          <div>
            <div className="font-medium">Schema drift detected</div>
            <div className="text-xs">
              Missing views: {health.missing_views.join(", ") || "none"} · Missing fields:{" "}
              {health.missing_fields.join(", ") || "none"}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="mt-6 flex flex-wrap gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
          <input
            placeholder="Search name or SR…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] py-2 pl-9 pr-4 text-sm outline-none focus:ring-2 focus:ring-[var(--accent)]/20"
          />
        </div>
        <select value={archetype} onChange={(e) => setArchetype(e.target.value)}
          className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm">
          <option value="">All archetypes</option>
          <option value="individual">Individual</option>
          <option value="corporate">Corporate</option>
          <option value="dao">DAO</option>
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm">
          <option value="">All statuses</option>
          <option value="not_started">Not started</option>
          <option value="in_review">In review</option>
          <option value="flagged">Flagged</option>
          <option value="blocked">Blocked</option>
          <option value="license_issued">License Issued</option>
        </select>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="mt-10 text-sm text-[var(--muted)]">Loading…</div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((c) => (
            <Link
              key={c.sr}
              href={`/companies/${c.sr}`}
              className="group rounded-xl border border-[var(--border)] bg-[var(--background)] p-5 transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-semibold group-hover:text-[var(--accent)]">{c.name}</div>
                  <div className="mt-0.5 font-mono text-xs text-[var(--muted)]">{c.sr}</div>
                </div>
                <StatusChip status={c.status} />
              </div>
              <p className="mt-3 line-clamp-2 text-sm text-[var(--muted)]">{c.activity}</p>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <ArchetypeBadge archetype={c.archetype} />
                <RiskChip tier={c.risk_tier} />
                {c.premium && <PremiumChip />}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
