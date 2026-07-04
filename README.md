# Compliance — Agent Console

Single-tenant demo. An operator opens one of **15 seeded company profiles**, loads that company's
documents, verifies passports, and runs a **four-stage LangGraph pipeline** (DVO → Compliance → Lease →
Registry & Licensing) that resolves to **License Issued**, **Flagged**, or **Blocked**. Passport
verification adds OpenCV face matching + document field extraction.

The data layer reads through stable Postgres views (`v_*`) and a repository adapter, so moving from local
Postgres to Supabase is a config change (`DATA_SOURCE` / `STORAGE`), not a rewrite.

## Stack

- **Frontend:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4, lucide-react, axios, SSE.
  Visual language mirrors the reference internal-assistant app.
- **Backend:** FastAPI (Python 3.11), SQLAlchemy 2, Pydantic v2, LangGraph, OpenCV (YuNet + SFace),
  optional OpenRouter (Claude Sonnet) for narrative.
- **DB now:** local Postgres. **Storage now:** local filesystem under `./storage`.

## Prerequisites

- Local **PostgreSQL** running on `:5432` (`pg_isready` should succeed). No Docker required.
- **Python 3.11** (`python3.11` on PATH) and **Node 18+ / npm**.
- Optional: `tesseract` (only if you want real OCR on real passport images; the demo does not need it).

## Setup

```bash
make setup      # creates rak role+db, runs migration, builds venv, seeds, npm install
```

Or step by step:

```bash
make db         # create rak role + database in local Postgres
make migrate    # apply backend/db/migrations/0001_init.sql (idempotent)
make venv       # python3.11 venv + pip install
make seed       # upsert 15 companies + people (reads files/_INDEX.csv)
cd frontend && npm install
```

Copy `.env.example` to `.env` and adjust if needed (defaults work out of the box):

```
DATABASE_URL=postgresql://rak:rak@localhost:5432/rak
REVIEW_DATE=2026-01-15
FACE_MATCH_THRESHOLD=0.363
AUTO_ESCALATE=true
DATASET_ROOT=<repo>/files/RAK_Compliance_Demo_Documents
```

> **Note on the `rak` role:** if you prefer to use your OS Postgres user instead of creating a `rak` role,
> set `DATABASE_URL=postgresql://<you>@localhost:5432/rak` and run `createdb rak` yourself.

## Run

```bash
make backend    # FastAPI on http://localhost:8000  (--reload)
make frontend   # Next.js on http://localhost:3000  (proxies /api -> :8000)
```

Open http://localhost:3000.

## Process flow (per-page stepper)

Each company's compliance is presented as a **per-page stepper**:

```
KYC  →  DVO  →  Compliance & Risk  →  Lease  →  Registry & Licensing
```

- **KYC** (`/companies/{sr}/kyc`) — per person: upload a passport image and take a **live device-camera
  photo** (`getUserMedia`); OpenCV (YuNet + SFace) matches the two faces and checks passport validity.
  A synthetic PDF has no photo, so without real images the match falls back to a deterministic verdict
  from the document fields. "Proceed to DVO" starts the run.
- **DVO / Compliance / Lease / Registry & Licensing** — each stage is its own page
  (`/companies/{sr}/process/{runId}/{stage}`). **Nothing runs up front**: a stage's check executes only when
  you land on its page (SSE `…/stages/{stage}/stream`), and its content streams in **bit by bit** —
  documents reviewed, then the decision/detail, escalations (with pacing), then the reasoning word-by-word
  and insights one-by-one. Prerequisite stages compute silently if you jump ahead; stages after a terminal
  flag/block show "not reached". The rail lights up as stages complete.
- **Insights & reasoning** per stage come from OpenRouter (Claude) when `OPENROUTER_API_KEY` is set
  (badge "Claude via OpenRouter"), else a deterministic rules-based fallback.

## Demo script (5 minutes)

1. **Sarvam AI** → *Load portal + customer documents* → *Start compliance checks* → on **KYC**, upload a
   passport + capture a selfie → *Verify* (Verified) → *Proceed to DVO* → step through the four stages →
   **License Issued**. (Happy path.)
2. **Fireblocks** → KYC shows passport expiry < 6 months → *Proceed* → **DVO Flagged**. (Document defect.)
3. **Krafton** → KYC checked → Compliance escalates CO → Senior → Director → **R&L Blocked**: gaming
   pre-approval missing. (Regulatory gate.)
4. **Cohere** → escalation-path archetype but auto-clears → **License Issued**. (Escalation ≠ rejection.)
5. Open **Audit Trail** → *Download decision summary*.

## Creating a dummy passport that passes KYC

KYC passes only when **both** hold:

1. **Face match** — the passport contains a face that matches your live selfie (OpenCV cosine
   score ≥ `FACE_MATCH_THRESHOLD`, default 0.363).
2. **Validity** — the passport expiry is **≥ 6 months after the review date** (`2026-01-15`), i.e.
   **≥ 2026-07-15**, and not expired.

Pointers, easiest first:

- **Easiest (no face needed).** Pick a company whose seeded person already has a valid passport
  (Sarvam, Krutrim, Ati Motors, GenRobotics, HealthifyMe, Cohere, Mistral). Upload *any* image/PDF as the
  passport and take any selfie. When no face is detected the check falls back to the passport's validity,
  which is valid for these — so it verifies. (Fireblocks/Jupiter stay flagged: their expiry/PoA are bad by design.)

- **Real face match (recommended for the demo).** Use a real, photo-realistic face — **your own photo**,
  or an **AI-generated face** (a "this-person-does-not-exist"–style image). Never use a real third party's
  passport photo. Two ways:
  - Upload that face image *as the passport* (PNG/JPG) and take a live selfie of the **same** person →
    real OpenCV match passes; validity falls back to the (valid) seeded record.
  - Or generate a self-contained passport PDF with the face embedded **and** a valid expiry:
    ```bash
    cd backend
    .venv/bin/python tools/make_dummy_passport.py \
      --face /path/to/your_face.jpg --name "Test Founder" --expiry 2032-01-01 \
      --out dummy_passport.pdf
    ```
    Upload `dummy_passport.pdf` on the KYC screen and take a live selfie of the same face → both checks pass.

Key facts: expiry must be a real date `≥ 2026-07-15`; the face must be photo-realistic (YuNet must detect
it); the selfie and passport must be the **same** person for the score to clear the threshold.

## Acceptance oracle (Section 9)

```bash
make test       # runs all 15 companies headless, asserts the exact end states
```

At `REVIEW_DATE=2026-01-15`: **7 License Issued**, **2 Flagged at DVO** (Fireblocks passport < 6 months;
Jupiter member-1 passport expired + PoA stale), **6 Blocked at R&L** (premium/DAO pre-approval).

## Architecture — the data-layer seam

```
Next.js -> /api/v1 (stable contract) -> Pydantic domain models
                                          |
                                mappers.py + mapping.yaml
                                          |
                                 Repository interface
                                    /            \
                          LocalRepository   SupabaseRepository (stub)
                                    \            /
                                Postgres VIEWS (v_*)  ->  base tables
```

The app selects only from `v_*` views in local mode. Two data sources are supported via `DATA_SOURCE`.

### Data sources

- **`DATA_SOURCE=local`** (default) — the 15 seeded demo companies in local Postgres.
- **`DATA_SOURCE=supabase`** — reads companies/people/documents **live** from a Supabase customer-portal
  project (`customer_portal`, `shareholders`, `documents`; files in the `application-files` bucket). The
  `domain` field maps to archetype/risk/premium/token/pre-approval; a shareholder's address-proof
  `uploaded_at` is used as the PoA date. **All pipeline state (runs, KYC verifications, stage results,
  lease/licence, audit, the verified list) stays in local Postgres** — the portal DB is read-only. Each
  company/its people are mirrored into the local tables on demand so the existing schema/FKs are untouched.

  To enable: fill `.env` with `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY`, set `DATA_SOURCE=supabase` (keep `STORAGE=local`), restart the backend.

## New in this build

- **KYC → DVO coupling.** DVO strictly depends on KYC: a person clears DVO only if their KYC
  passport-verification is `verified`. A flagged KYC fails DVO (carrying the reason); no KYC → `kyc_incomplete`.
- **Full audit report (PDF).** Audit tab → *Download full audit report (PDF)* →
  `GET /api/v1/companies/{sr}/audit/report` renders company, parties, KYC/DVO, risk + escalation, lease,
  R&L decision, per-stage reasoning/insights, final verdict, and the action log (reportlab).
- **Verified list (DB).** A `company_verifications` table records which companies are verified vs not on run
  completion; query it at `GET /api/v1/verifications`.

## Honest flags

- Face match needs real images with faces; the synthetic passports have none, so a deterministic fallback
  keeps the oracle reproducible. Drop real test images at runtime to exercise the real OpenCV path.
- OCR on the synthetic PDFs is trivially clean and not representative of production scans.
- DVO and the risk gate are deterministic rules (auditable); the LLM adds document-reading and narrative.
- Escalation and pre-approval are simulated status fields — no real regulator integration.

## Repository layout

```
backend/   FastAPI app, rules, vision, LangGraph pipeline, migration + seed, oracle test
frontend/  Next.js App Router screens + components + typed API client
files/     the 15-company dataset (228 synthetic PDFs) + _INDEX.csv
storage/   local StorageAdapter root (raw-documents, passport-images, selfies, generated-outputs)
```
