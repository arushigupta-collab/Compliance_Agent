-- 0002: additive only. The 0001 schema is unchanged.
-- One new table: the list of which companies are verified or not, populated
-- when a compliance run completes.
create table if not exists company_verifications (
  company_id  uuid primary key,
  sr          text,
  name        text,
  status      text not null,                 -- license_issued | flagged | blocked | ...
  verified    boolean not null default false,
  last_run_id uuid,
  reason      text,
  decided_at  timestamptz not null default now()
);

create index if not exists company_verifications_verified_idx on company_verifications(verified);
