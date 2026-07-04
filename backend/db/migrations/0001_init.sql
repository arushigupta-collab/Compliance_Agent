-- RAK DAO Compliance Console — initial schema (idempotent, additive).
-- The app reads ONLY the v_* views; base tables may change behind them.
create extension if not exists "uuid-ossp";

create table if not exists companies (
  id uuid primary key default uuid_generate_v4(),
  sr text unique not null,
  name text not null,
  archetype text not null,                 -- individual | corporate | dao
  company_type text not null,
  activity text not null,
  activity_class text not null,
  risk_tier text not null,                 -- LOW | LOW-MEDIUM | MEDIUM | MEDIUM-HIGH | HIGH
  jurisdiction text,
  package text not null,
  visa_quota int not null default 1,
  premium boolean not null default false,
  token_issuing boolean not null default false,
  preapproval_status text,
  status text not null default 'not_started',  -- not_started|in_review|flagged|blocked|license_issued
  attributes jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists company_people (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  name text not null, role text not null, nationality text,
  dob date, pob text,
  passport_no text, passport_issue date, passport_expiry date, issuing_authority text,
  address text, poa_source text, poa_date date,
  ubo_pct text, is_ubo boolean default false, is_signatory boolean default false,
  attributes jsonb not null default '{}'
);

create table if not exists document_uploads (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  doc_key text not null,                   -- stable requirement key, e.g. G01, U03
  source text not null,                    -- generated | uploaded
  filename text, storage_path text,
  status text not null default 'missing',  -- missing | uploaded | extracted
  extracted_fields jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (company_id, doc_key)
);

create table if not exists passport_verifications (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  person_id uuid references company_people(id) on delete cascade,
  passport_image_path text, selfie_path text,
  mrz jsonb default '{}', extracted jsonb default '{}',
  face_match_score numeric, checks jsonb default '{}',
  overall text,                            -- verified | flagged
  created_at timestamptz not null default now()
);

create table if not exists compliance_runs (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id) on delete cascade,
  status text not null default 'running',
  started_at timestamptz not null default now(),
  finished_at timestamptz, summary jsonb default '{}'
);

create table if not exists stage_results (
  id uuid primary key default uuid_generate_v4(),
  run_id uuid references compliance_runs(id) on delete cascade,
  stage text not null,                     -- dvo | compliance | lease | rnl
  decision text not null,                  -- passed | flagged | blocked | escalated | auto_approved
  risk_score numeric, exceptions jsonb default '[]', detail jsonb default '{}',
  created_at timestamptz not null default now()
);

create table if not exists escalations (
  id uuid primary key default uuid_generate_v4(),
  run_id uuid references compliance_runs(id) on delete cascade,
  level text not null,                     -- officer | senior | director
  status text not null default 'pending',  -- pending | approved | rejected
  decided_by text, decided_at timestamptz
);

create table if not exists lease_records (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id), run_id uuid references compliance_runs(id),
  package text, term text, visa_quota int, fee text, crm_ref text,
  status text default 'created', created_at timestamptz not null default now()
);

create table if not exists licenses (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid references companies(id), run_id uuid references compliance_runs(id),
  cert_no text, license_no text, establishment_card_no text,
  documents_visible boolean default false, issued_at timestamptz
);

create table if not exists audit_log (
  id uuid primary key default uuid_generate_v4(),
  company_id uuid, run_id uuid, actor text, action text,
  payload jsonb default '{}', created_at timestamptz not null default now()
);

-- ---- Stable views: the contract seam ----
create or replace view v_companies as
  select id, sr, name, archetype, company_type, activity, activity_class,
         risk_tier, jurisdiction, package, visa_quota, premium, token_issuing,
         preapproval_status, status, attributes
  from companies;

create or replace view v_company_people as
  select id, company_id, name, role, nationality, dob, pob,
         passport_no, passport_issue, passport_expiry, issuing_authority,
         address, poa_source, poa_date, ubo_pct, is_ubo, is_signatory, attributes
  from company_people;

create or replace view v_document_status as
  select company_id, doc_key, source, status, filename, extracted_fields
  from document_uploads;

create or replace view v_run_summary as
  select r.id as run_id, r.company_id, r.status, r.started_at, r.finished_at,
         coalesce(jsonb_agg(jsonb_build_object('stage', s.stage,'decision', s.decision,
           'risk', s.risk_score,'exceptions', s.exceptions,'detail', s.detail) order by s.created_at)
           filter (where s.id is not null), '[]') as stages
  from compliance_runs r left join stage_results s on s.run_id = r.id
  group by r.id;
