import { Building2, User, Boxes } from "lucide-react";

const STATUS_STYLES: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300",
  in_review: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  flagged: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  blocked: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  license_issued: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
};
const STATUS_LABELS: Record<string, string> = {
  not_started: "Not started",
  in_review: "In review",
  flagged: "Flagged",
  blocked: "Blocked",
  license_issued: "License Issued",
};

export function StatusChip({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? STATUS_STYLES.not_started}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

const RISK_STYLES: Record<string, string> = {
  LOW: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  "LOW-MEDIUM": "bg-lime-50 text-lime-700 dark:bg-lime-950 dark:text-lime-300",
  MEDIUM: "bg-yellow-50 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-300",
  "MEDIUM-HIGH": "bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
  HIGH: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
};

export function RiskChip({ tier }: { tier: string }) {
  const k = tier.trim().toUpperCase();
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${RISK_STYLES[k] ?? RISK_STYLES.MEDIUM}`}>
      {k}
    </span>
  );
}

const ARCH = {
  individual: { icon: User, label: "Individual" },
  corporate: { icon: Building2, label: "Corporate" },
  dao: { icon: Boxes, label: "DAO" },
} as const;

export function ArchetypeBadge({ archetype }: { archetype: "individual" | "corporate" | "dao" }) {
  const a = ARCH[archetype] ?? ARCH.individual;
  const Icon = a.icon;
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-0.5 text-xs font-medium text-[var(--muted)]">
      <Icon size={12} /> {a.label}
    </span>
  );
}

export function PremiumChip() {
  return (
    <span className="inline-flex items-center rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700 dark:bg-violet-950 dark:text-violet-300">
      Premium
    </span>
  );
}
