"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, BadgeCheck, FileText, ShieldAlert, ShieldCheck, Upload } from "lucide-react";
import { CompanyProfile, PassportVerification, Person, getProfile, startRun, verifyPassport } from "@/lib/api";
import { CameraCapture } from "@/components/CameraCapture";
import { StageRail } from "@/components/StageRail";

export default function KycPage({ params }: { params: Promise<{ sr: string }> }) {
  const { sr } = use(params);
  const router = useRouter();
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [starting, setStarting] = useState(false);

  const refresh = useCallback(() => getProfile(sr).then(setProfile), [sr]);
  useEffect(() => { refresh(); }, [refresh]);

  if (!profile) return <div className="px-8 py-8 text-sm text-[var(--muted)]">Loading…</div>;
  const c = profile.company;
  const pvByPerson: Record<string, PassportVerification> = {};
  profile.passport_verifications.forEach((pv) => { pvByPerson[pv.person_id] = pv; });

  const docsMissing = profile.checklist.filter((r) => r.required && r.status !== "extracted");
  const allChecked = profile.people.every((p) => pvByPerson[p.id]);
  const canProceed = allChecked && docsMissing.length === 0;

  const proceed = async () => {
    setStarting(true);
    try {
      const r = await startRun(sr);
      router.push(`/companies/${sr}/process/${r.run_id}/dvo`);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-[var(--border)] bg-[var(--surface)] px-8 pb-5 pt-5">
        <Link href={`/companies/${sr}`} className="mb-3 inline-flex items-center gap-1 text-sm text-[var(--muted)] hover:text-[var(--foreground)]">
          <ArrowLeft size={14} /> Back to profile
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">KYC — Identity Verification</h1>
            <div className="mt-1 text-sm text-[var(--muted)]">
              <span className="font-medium text-[var(--foreground)]">{c.name}</span> · <span className="font-mono">{c.sr}</span>
            </div>
          </div>
          <button
            onClick={proceed}
            disabled={!canProceed || starting}
            title={canProceed ? "Start the compliance pipeline" : docsMissing.length ? `Documents missing: ${docsMissing.map((d) => d.doc_key).join(", ")}` : "Verify every person's passport first"}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-opacity ${
              !canProceed || starting ? "cursor-not-allowed bg-gray-200 text-gray-400 dark:bg-gray-800 dark:text-gray-600" : "bg-[var(--accent)] text-white hover:opacity-90"
            }`}
          >
            {starting ? "Starting…" : "Proceed to DVO"} <ArrowRight size={16} />
          </button>
        </div>
        <div className="mt-4">
          <StageRail state={{ current: "kyc", status: { kyc: "current" }, hrefFor: () => null }} />
        </div>
      </div>

      <div className="flex-1 overflow-auto px-8 py-6">
        <p className="mb-4 max-w-3xl text-sm text-[var(--muted)]">
          Upload each person&apos;s passport and take a live photo with your device camera. OpenCV (YuNet + SFace)
          matches the two faces and checks passport validity. A synthetic passport PDF has no photo — upload a real
          face image to exercise the real match, or the demo falls back to a deterministic verdict from the document fields.
        </p>
        {docsMissing.length > 0 && (
          <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
            {docsMissing.length} required document(s) still missing — load them on the{" "}
            <Link href={`/companies/${sr}`} className="underline">profile</Link> before proceeding.
          </div>
        )}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {profile.people.map((p) => (
            <KycPersonCard key={p.id} sr={sr} person={p} pv={pvByPerson[p.id]} onChange={refresh} />
          ))}
        </div>
      </div>
    </div>
  );
}

function KycPersonCard({ sr, person, pv, onChange }: { sr: string; person: Person; pv?: PassportVerification; onChange: () => void }) {
  const passportRef = useRef<HTMLInputElement>(null);
  const [passportImg, setPassportImg] = useState<File | null>(null);
  const [passportPreview, setPassportPreview] = useState<string | null>(null);
  const [selfie, setSelfie] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  const verified = pv?.overall === "verified";
  const score = pv?.face_match_score;
  const threshold = pv?.checks?.face_threshold ?? 0.363;
  const checks = pv?.checks ?? {};

  const isPdf = !!passportImg && (passportImg.type === "application/pdf" || passportImg.name.toLowerCase().endsWith(".pdf"));
  const onPassport = (f: File) => {
    setPassportImg(f);
    const pdf = f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
    setPassportPreview(pdf ? null : URL.createObjectURL(f));
  };

  const verify = async () => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("person_id", person.id);
      if (passportImg) fd.append("passport_image", passportImg);
      if (selfie) fd.append("selfie", selfie);
      await verifyPassport(sr, fd);
      await onChange();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="font-semibold">{person.name}</div>
          <div className="text-xs text-[var(--muted)]">{person.role}</div>
        </div>
        {pv && (
          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${verified ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300"}`}>
            {verified ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}{verified ? "Verified" : "Flagged"}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        {/* Passport */}
        <div className="rounded-lg border border-[var(--border)] p-2">
          <div className="mb-1 text-xs font-medium text-[var(--muted)]">Passport (PDF or image)</div>
          <div className="relative aspect-[4/3] w-full overflow-hidden rounded-md bg-[var(--surface)]">
            {passportPreview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={passportPreview} alt="Passport" className="h-full w-full object-cover" />
            ) : isPdf ? (
              <div className="flex h-full flex-col items-center justify-center gap-1 text-xs text-[var(--muted)]">
                <FileText size={22} />
                <span className="max-w-[90%] truncate px-2">{passportImg?.name}</span>
                <span className="rounded bg-[var(--background)] px-1.5 py-0.5 text-[10px] font-medium">PDF</span>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-[var(--muted)]">No file</div>
            )}
          </div>
          <button onClick={() => passportRef.current?.click()}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--foreground)]">
            <Upload size={14} /> {passportImg ? "Replace" : "Upload"}
          </button>
          <input ref={passportRef} type="file" accept="application/pdf,.pdf,image/png,image/jpeg,image/*" className="hidden"
            onChange={(e) => e.target.files?.[0] && onPassport(e.target.files[0])} />
        </div>

        {/* Live camera */}
        <div>
          <div className="mb-1 text-xs font-medium text-[var(--muted)]">Live photo</div>
          <CameraCapture onCapture={(f) => setSelfie(f)} />
        </div>
      </div>

      {/* Result */}
      {pv && (
        <div className="mt-3 space-y-2">
          {score != null && (
            <div>
              <div className="flex justify-between text-xs text-[var(--muted)]">
                <span>Face match score</span><span className="font-mono">{score.toFixed(3)} (thr {threshold})</span>
              </div>
              <div className="relative mt-1 h-2 rounded-full bg-gray-200 dark:bg-gray-800">
                <div className={`h-2 rounded-full ${score >= threshold ? "bg-emerald-500" : "bg-red-500"}`}
                  style={{ width: `${Math.min(100, Math.max(4, score * 100))}%` }} />
                <div className="absolute top-0 h-2 w-0.5 bg-black/50" style={{ left: `${threshold * 100}%` }} />
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-1 text-xs">
            <Chk ok={checks.expiry_ok} label={`Expiry ≥ 6mo${checks.expiry ? ` (${checks.expiry})` : ""}`} reason={checks.expiry_reason} />
            <Chk ok={checks.poa_ok} label={`PoA fresh${checks.poa_date ? ` (${checks.poa_date})` : ""}`} reason={checks.poa_reason} />
            <Chk ok={checks.name_match} label="Name match" />
            <Chk ok={checks.face_passed} label="Face match" reason={checks.face_reason} />
          </div>
        </div>
      )}

      <button onClick={verify} disabled={busy}
        className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50">
        <BadgeCheck size={14} /> {busy ? "Matching…" : pv ? "Re-verify" : "Verify identity"}
      </button>
    </div>
  );
}

function Chk({ ok, label, reason }: { ok?: boolean; label: string; reason?: string | null }) {
  return (
    <div className={`flex items-center gap-1 ${ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
      <span>{ok ? "✓" : "✗"}</span>
      <span title={reason ?? undefined}>{label}{!ok && reason ? ` — ${reason}` : ""}</span>
    </div>
  );
}
