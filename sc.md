-- Customer Portal — Company Incorporation Flow
-- Run this in the Supabase SQL editor (or via `supabase db push`) on a fresh project.
-- Order matters: enums → tables → indexes → policies.

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
do $$ begin
  create type application_status as enum (
    'draft', 'in_review', 'submitted', 'approved', 'rejected'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  -- Canonical values for the current 4-step flow: company → founders → sign → submit → complete.
  -- The older values (review, payment, shareholders, documents, forms) are kept so historical
  -- rows created before the flow was simplified remain valid, but only the five above are used
  -- by new applications.
  create type application_step as enum (
    'company', 'founders', 'sign', 'submit', 'complete',
    'review', 'payment', 'shareholders', 'documents', 'forms'
  );
exception when duplicate_object then null; end $$;

-- Older installs already have the enum without the current-flow values.
-- ADD VALUE IF NOT EXISTS is idempotent (Postgres 12+).
do $$ begin
  alter type application_step add value if not exists 'company';
  alter type application_step add value if not exists 'founders';
  alter type application_step add value if not exists 'sign';
end $$;

do $$ begin
  create type payment_status as enum (
    'unpaid', 'processing', 'paid', 'failed', 'refunded'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type document_kind as enum (
    'required',    -- KYC-type docs the founder supplies (passport, address proof)
    'signed_form', -- a template we generated that the customer signed and uploaded back
    'shareholder'  -- docs attached to a specific shareholder row
  );
exception when duplicate_object then null; end $$;

-- Older installs may already have the enum without the newest value; add it if missing.
do $$ begin
  alter type document_kind add value if not exists 'shareholder';
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------------
-- packages: what a customer is buying
-- ---------------------------------------------------------------------------
create table if not exists packages (
  id           uuid primary key default gen_random_uuid(),
  slug         text unique not null,
  name         text not null,
  tagline      text,
  description  text,
  price_cents  integer not null check (price_cents >= 0),
  currency     text not null default 'USD',
  features     jsonb not null default '[]'::jsonb,   -- array of strings
  is_active    boolean not null default true,
  sort_order   integer not null default 0,
  created_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- required_document_types: what docs the customer must upload
-- ---------------------------------------------------------------------------
create table if not exists required_document_types (
  id                 uuid primary key default gen_random_uuid(),
  key                text unique not null,
  label              text not null,
  description        text,
  is_required        boolean not null default true,
  applicable_domains jsonb not null default '[]'::jsonb,  -- array of domain keys; empty = all domains
  sort_order         integer not null default 0
);

-- Alter for existing installs.
do $$ begin
  alter table required_document_types add column if not exists applicable_domains jsonb not null default '[]'::jsonb;
end $$;

-- ---------------------------------------------------------------------------
-- form_templates: pre-built forms customer downloads, signs, uploads back
-- body is HTML with {{placeholders}} that get substituted at render time.
-- ---------------------------------------------------------------------------
create table if not exists form_templates (
  id                 uuid primary key default gen_random_uuid(),
  key                text unique not null,
  title              text not null,
  description        text,
  body_html          text not null,
  -- "general" templates are shown to every applicant.
  -- "compliance" templates are shown only when the app's domain matches.
  category           text not null default 'general',
  applicable_domains jsonb not null default '[]'::jsonb,   -- array of domain keys
  sort_order         integer not null default 0,
  created_at         timestamptz not null default now()
);

-- Alter statements for existing installs.
do $$ begin
  alter table form_templates add column if not exists category text not null default 'general';
  alter table form_templates add column if not exists applicable_domains jsonb not null default '[]'::jsonb;
end $$;

-- ---------------------------------------------------------------------------
-- customer_portal: one row per customer submission-in-progress
-- ---------------------------------------------------------------------------
create table if not exists customer_portal (
  id                    uuid primary key default gen_random_uuid(),
  package_id            uuid references packages(id) on delete set null,
  status                application_status not null default 'draft',
  current_step          application_step not null default 'company',
  -- Company details captured along the way (kept flat for simplicity)
  company_name          text,     -- proposed name (customer-entered)
  company_type          text,     -- e.g. FZ-LLC, FZ-Establishment, Branch
  contact_name          text,
  contact_email         text,
  contact_phone         text,
  -- Inventory / visas / add-ons — populated either by Sales upstream or by the
  -- customer on the Review step in self-serve mode.
  inventory_type        text,     -- shared_desk | dedicated_desk | office
  visa_count            integer not null default 0 check (visa_count >= 0),
  addons                jsonb not null default '[]'::jsonb,   -- array of add-on keys
  -- Flags populated upstream (Sales/CRM) but visible to the portal
  high_risk_activity    boolean not null default false,       -- gates Source-of-Wealth doc
  is_prepaid            boolean not null default false,       -- Sales generated a payment link the customer already paid
  proposed_name_status  text not null default 'pending',      -- pending | approved | rejected (out of portal scope, tracked only)
  -- Business ICP; drives which compliance templates the customer sees on the Sign step.
  domain                text,                                 -- standard_fz_llc | subsidiary_foreign | premium_regulated | startup_dao | alpha_dao
  -- Additional proposed names (primary lives in company_name).
  company_name_alt_1    text,
  company_name_alt_2    text,
  -- Business essentials captured on the Company step.
  preferred_currency    text,     -- AED | USD | EUR
  financial_year_end    text,     -- December | March | June | Other
  commencement_date     date,
  revenue_bracket       text,     -- key from REVENUE_BRACKET_OPTIONS
  target_markets        jsonb not null default '[]'::jsonb,   -- array of ISO country codes
  business_description  text,     -- 200-500 chars, feeds activity mapping
  -- Primary contact extras
  contact_role          text,     -- key from CONTACT_ROLE_OPTIONS
  contact_channel       text,     -- key from CONTACT_CHANNEL_OPTIONS
  contact_language      text,     -- key from LANGUAGE_OPTIONS
  -- Manager / Director details (0 or 1 per application, jsonb object)
  manager               jsonb,
  -- Authorised signatories (0 or more per application)
  authorized_signatories jsonb not null default '[]'::jsonb,
  -- Sales handoff — points to closed_deals.id. install.sql runs closed_deals.sql
  -- before schema.sql so the FK can be enforced on a fresh install.
  closed_deal_id        uuid references closed_deals(id) on delete set null,
  notes                 text,
  submitted_at          timestamptz,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- Alter statements for anyone re-running against an older install (idempotent).
do $$ begin
  alter table customer_portal add column if not exists inventory_type       text;
  alter table customer_portal add column if not exists visa_count           integer not null default 0;
  alter table customer_portal add column if not exists addons               jsonb not null default '[]'::jsonb;
  alter table customer_portal add column if not exists high_risk_activity   boolean not null default false;
  alter table customer_portal add column if not exists is_prepaid           boolean not null default false;
  alter table customer_portal add column if not exists proposed_name_status text not null default 'pending';
  alter table customer_portal add column if not exists domain               text;
  alter table customer_portal add column if not exists company_name_alt_1   text;
  alter table customer_portal add column if not exists company_name_alt_2   text;
  alter table customer_portal add column if not exists preferred_currency   text;
  alter table customer_portal add column if not exists financial_year_end   text;
  alter table customer_portal add column if not exists commencement_date    date;
  alter table customer_portal add column if not exists revenue_bracket      text;
  alter table customer_portal add column if not exists target_markets       jsonb not null default '[]'::jsonb;
  alter table customer_portal add column if not exists business_description text;
  alter table customer_portal add column if not exists contact_role         text;
  alter table customer_portal add column if not exists contact_channel      text;
  alter table customer_portal add column if not exists contact_language     text;
  alter table customer_portal add column if not exists manager              jsonb;
  alter table customer_portal add column if not exists authorized_signatories jsonb not null default '[]'::jsonb;
  -- If closed_deal_id already exists as text from an older install, drop it
  -- manually before re-running: `alter table customer_portal drop column closed_deal_id;`
  alter table customer_portal add column if not exists closed_deal_id       uuid references closed_deals(id) on delete set null;
  -- Fix the default step for anyone whose table was created before the 4-step flow.
  alter table customer_portal alter column current_step set default 'company';
end $$;

create index if not exists customer_portal_closed_deal_idx on customer_portal(closed_deal_id);

create index if not exists customer_portal_status_idx on customer_portal(status);
create index if not exists customer_portal_created_at_idx on customer_portal(created_at desc);

-- ---------------------------------------------------------------------------
-- shareholders
-- ---------------------------------------------------------------------------
create table if not exists shareholders (
  id                                  uuid primary key default gen_random_uuid(),
  application_id                      uuid not null references customer_portal(id) on delete cascade,
  -- Identity
  shareholder_type                    text not null default 'individual',   -- individual | corporate
  full_name                           text not null,
  date_of_birth                       date,
  nationality                         text,       -- ISO country code
  second_nationality                  text,       -- ISO country code
  country_of_residence                text,       -- ISO country code
  -- Contact
  email                               text,
  mobile_number                       text,
  -- Address
  residential_address                 text,
  city                                text,
  postal_code                         text,
  -- Passport
  passport_number                     text,
  passport_issue_date                 date,
  passport_expiry_date                date,
  passport_issuing_country            text,       -- ISO country code
  -- Emirates ID (conditional on UAE residence)
  emirates_id_number                  text,
  emirates_id_expiry                  date,
  -- Ownership & wealth
  ownership_percent                   numeric(5,2) not null check (ownership_percent >= 0 and ownership_percent <= 100),
  source_of_wealth                    text,       -- key from SOURCE_OF_WEALTH_OPTIONS
  source_of_wealth_detail             text,
  -- Roles & flags
  is_director                         boolean not null default false,
  is_manager                          boolean not null default false,
  is_authorized_signatory             boolean not null default false,
  is_pep                              boolean not null default false,
  is_us_person                        boolean not null default false,
  -- Legacy KYC field (kept for backwards compatibility)
  id_number                           text,
  -- Corporate shareholders (only when shareholder_type = 'corporate')
  corporate_company_name              text,
  corporate_country_of_incorporation  text,       -- ISO country code
  corporate_registration_number       text,
  corporate_registered_address        text,
  corporate_ubo_details               text,
  created_at                          timestamptz not null default now()
);

create index if not exists shareholders_application_idx on shareholders(application_id);

-- Idempotent alter statements for older installs.
do $$ begin
  alter table shareholders add column if not exists shareholder_type                    text not null default 'individual';
  alter table shareholders add column if not exists date_of_birth                       date;
  alter table shareholders add column if not exists second_nationality                  text;
  alter table shareholders add column if not exists country_of_residence                text;
  alter table shareholders add column if not exists mobile_number                       text;
  alter table shareholders add column if not exists residential_address                 text;
  alter table shareholders add column if not exists city                                text;
  alter table shareholders add column if not exists postal_code                         text;
  alter table shareholders add column if not exists passport_number                     text;
  alter table shareholders add column if not exists passport_issue_date                 date;
  alter table shareholders add column if not exists passport_expiry_date                date;
  alter table shareholders add column if not exists passport_issuing_country            text;
  alter table shareholders add column if not exists emirates_id_number                  text;
  alter table shareholders add column if not exists emirates_id_expiry                  date;
  alter table shareholders add column if not exists source_of_wealth                    text;
  alter table shareholders add column if not exists source_of_wealth_detail             text;
  alter table shareholders add column if not exists is_manager                          boolean not null default false;
  alter table shareholders add column if not exists is_authorized_signatory             boolean not null default false;
  alter table shareholders add column if not exists is_pep                              boolean not null default false;
  alter table shareholders add column if not exists is_us_person                        boolean not null default false;
  alter table shareholders add column if not exists corporate_company_name              text;
  alter table shareholders add column if not exists corporate_country_of_incorporation  text;
  alter table shareholders add column if not exists corporate_registration_number       text;
  alter table shareholders add column if not exists corporate_registered_address        text;
  alter table shareholders add column if not exists corporate_ubo_details               text;
end $$;

-- ---------------------------------------------------------------------------
-- documents: uploaded files (both required KYC docs and signed templates)
-- files live in Supabase Storage bucket 'application-files'
-- ---------------------------------------------------------------------------
create table if not exists documents (
  id                uuid primary key default gen_random_uuid(),
  application_id    uuid not null references customer_portal(id) on delete cascade,
  kind              document_kind not null,
  -- Only set when kind = 'shareholder' — links the doc to a specific shareholder.
  shareholder_id    uuid references shareholders(id) on delete cascade,
  -- For 'required' docs: matches required_document_types.key
  -- For 'signed_form' docs: matches form_templates.key
  -- For 'shareholder' docs: 'passport' | 'address_proof' | ...
  type_key          text not null,
  file_name         text not null,
  storage_path      text not null,          -- path inside the bucket
  mime_type         text,
  size_bytes        bigint,
  uploaded_at       timestamptz not null default now()
);

-- Uniqueness rules:
-- * Founder docs & signed forms: one file per (application, kind, type_key).
-- * Shareholder docs: one file per (shareholder, type_key).
create unique index if not exists documents_founder_slot_uniq
  on documents(application_id, kind, type_key)
  where kind in ('required','signed_form');
create unique index if not exists documents_shareholder_slot_uniq
  on documents(shareholder_id, type_key)
  where kind = 'shareholder';

create index if not exists documents_application_idx on documents(application_id);
create index if not exists documents_shareholder_idx on documents(shareholder_id);

-- Alter statement so older installs pick up the new column.
do $$ begin
  alter table documents add column if not exists shareholder_id uuid references shareholders(id) on delete cascade;
end $$;

-- ---------------------------------------------------------------------------
-- payments: dummy record of the (fake) payment attempt
-- ---------------------------------------------------------------------------
create table if not exists payments (
  id              uuid primary key default gen_random_uuid(),
  application_id  uuid not null references customer_portal(id) on delete cascade,
  amount_cents    integer not null,
  currency        text not null default 'USD',
  method          text,                     -- 'card' | 'bank' | etc. (dummy)
  status          payment_status not null default 'unpaid',
  transaction_ref text,                     -- fake reference we generate client-side
  card_last4      text,
  card_brand      text,
  paid_at         timestamptz,
  created_at      timestamptz not null default now()
);

create index if not exists payments_application_idx on payments(application_id);

-- ---------------------------------------------------------------------------
-- updated_at trigger for customer_portal
-- ---------------------------------------------------------------------------
create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at := now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists customer_portal_set_updated_at on customer_portal;
create trigger customer_portal_set_updated_at
  before update on customer_portal
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- No auth is wired up yet, so we ship permissive policies that let the
-- anon key read/write. When auth lands, replace these with policies keyed
-- off auth.uid() (e.g., customer_portal.owner_id = auth.uid()).
-- ---------------------------------------------------------------------------
alter table packages                 enable row level security;
alter table required_document_types  enable row level security;
alter table form_templates           enable row level security;
alter table customer_portal             enable row level security;
alter table shareholders             enable row level security;
alter table documents                enable row level security;
alter table payments                 enable row level security;

do $$ begin
  create policy "read packages"                on packages                for select using (true);
  create policy "read required_document_types" on required_document_types for select using (true);
  create policy "read form_templates"          on form_templates          for select using (true);
exception when duplicate_object then null; end $$;

-- TEMPORARY: open access to application data (replace once auth is added)
do $$ begin
  create policy "open customer_portal"  on customer_portal  for all using (true) with check (true);
  create policy "open shareholders"  on shareholders  for all using (true) with check (true);
  create policy "open documents"     on documents     for all using (true) with check (true);
  create policy "open payments"      on payments      for all using (true) with check (true);
exception when duplicate_object then null; end $$;
