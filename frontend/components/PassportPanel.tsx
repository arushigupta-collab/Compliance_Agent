"use client";

import { useRef, useState } from "react";
import { BadgeCheck, Camera, ShieldAlert, ShieldCheck, Upload } from "lucide-react";
import { CompanyProfile, Person, PassportVerification, verifyPassport } from "@/lib/api";

export function PassportPanel({ profile, onChange }: { profile: CompanyProfile; onChange: () => void }) {
  const pvByPerson: Record<string, PassportVerification> = {};
  profile.passport_verifications.forEach((pv) => { pvByPerson[pv.person_id] = pv; });

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-5">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        Passport verification (OpenCV)
      </h2>
      <p className="mb-4 text-xs text-[var(--muted)]">
        Field checks run against document data. Face match uses a real image pair when supplied, else a
        deterministic demo fallback (synthetic passports have no photo).
      </p>
      <div className="space-y-3">
        {profile.people.map((p) => (
          <PersonRow key={p.id} sr={profile.company.sr} person={p} pv={pvByPerson[p.id]} onChange={onChange} />
        ))}
      </div>
    </section>
  );
}

function PersonRow({ sr, person, pv, onChange }: { sr: string; person: Person; pv?: PassportVerification; onChange: () => void }) {
  const passportRef = useRef<HTMLInputElement>(null);
  const selfieRef = useRef<HTMLInputElement>(null);
  const [passportImg, setPassportImg] = useState<File | null>(null);
  const [selfieImg, setSelfieImg] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("person_id", person.id);
      if (passportImg) fd.append("passport_image", passportImg);
      if (selfieImg) fd.append("selfie", selfieImg);
      await verifyPassport(sr, fd);
      await onChange();
    } finally {
      setBusy(false);
    }
  };

  const verified = pv?.overall === "verified";
  const flagged = pv?.overall === "flagged";
  const score = pv?.face_match_score;
  const threshold = pv?.checks?.face_threshold ?? 0.363;
  const checks = pv?.checks ?? {};

  return (
    <div className="rounded-lg border border-[var(--border)] p-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium">{person.name}</div>
          <div className="text-xs text-[var(--muted)]">{person.role}</div>
        </div>
        {pv && (
          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
            verified ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                     : "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300"}`}>
            {verified ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}
            {verified ? "Verified" : "Flagged"}
          </span>
        )}
      </div>

      {pv && (
        <div className="mt-3 space-y-2">
          {/* Score bar */}
          {score != null && (
            <div>
              <div className="flex justify-between text-xs text-[var(--muted)]">
                <span>Face match score</span>
                <span className="font-mono">{score.toFixed(3)} (thr {threshold})</span>
              </div>
              <div className="relative mt-1 h-2 rounded-full bg-gray-200 dark:bg-gray-800">
                <div className={`h-2 rounded-full ${score >= threshold ? "bg-emerald-500" : "bg-red-500"}`}
                  style={{ width: `${Math.min(100, Math.max(4, score * 100))}%` }} />
                <div className="absolute top-0 h-2 w-0.5 bg-black/50" style={{ left: `${threshold * 100}%` }} />
              </div>
            </div>
          )}
          {/* Field checks */}
          <div className="grid grid-cols-2 gap-1 text-xs">
            <Check ok={checks.expiry_ok} label={`Expiry ≥ 6mo${checks.expiry ? ` (${checks.expiry})` : ""}`} reason={checks.expiry_reason} />
            <Check ok={checks.poa_ok} label={`PoA fresh${checks.poa_date ? ` (${checks.poa_date})` : ""}`} reason={checks.poa_reason} />
            <Check ok={checks.name_match} label="Name match" />
            <Check ok={checks.face_passed} label="Face match" reason={checks.face_reason} />
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <ImgBtn label={passportImg ? "Passport ✓" : "Passport image"} icon={Upload}
          onClick={() => passportRef.current?.click()} />
        <ImgBtn label={selfieImg ? "Selfie ✓" : "Selfie"} icon={Camera}
          onClick={() => selfieRef.current?.click()} />
        <button onClick={run} disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50">
          <BadgeCheck size={14} /> {busy ? "Verifying…" : pv ? "Re-verify" : "Verify"}
        </button>
        <input ref={passportRef} type="file" accept="image/*" className="hidden"
          onChange={(e) => setPassportImg(e.target.files?.[0] ?? null)} />
        <input ref={selfieRef} type="file" accept="image/*" capture="user" className="hidden"
          onChange={(e) => setSelfieImg(e.target.files?.[0] ?? null)} />
      </div>
    </div>
  );
}

function Check({ ok, label, reason }: { ok?: boolean; label: string; reason?: string | null }) {
  return (
    <div className={`flex items-center gap-1 ${ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
      <span>{ok ? "✓" : "✗"}</span>
      <span title={reason ?? undefined}>{label}{!ok && reason ? ` — ${reason}` : ""}</span>
    </div>
  );
}

function ImgBtn({ label, icon: Icon, onClick }: { label: string; icon: any; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--foreground)]">
      <Icon size={14} /> {label}
    </button>
  );
}
