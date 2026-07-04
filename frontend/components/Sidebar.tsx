"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, ShieldCheck, FileText } from "lucide-react";

const NAV = [
  { label: "Company Directory", href: "/", icon: LayoutGrid },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)]">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
          <ShieldCheck size={18} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold">Compliance</div>
          <div className="text-xs text-[var(--muted)]">Agent Console</div>
        </div>
      </div>

      <nav className="flex-1 px-3">
        {NAV.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`mb-1 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-[var(--background)] font-medium text-[var(--foreground)] shadow-sm"
                  : "text-[var(--muted)] hover:bg-[var(--background)]/60 hover:text-[var(--foreground)]"
              }`}
            >
              <Icon size={16} /> {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-[var(--border)] px-5 py-4 text-xs text-[var(--muted)]">
        <div className="flex items-center gap-1.5">
          <FileText size={12} /> Review date 2026-01-15
        </div>
        <div className="mt-1">Demo · local Postgres</div>
      </div>
    </aside>
  );
}
