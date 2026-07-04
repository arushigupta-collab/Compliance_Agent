.PHONY: db migrate seed backend frontend test reset clean

DB_URL ?= postgresql://rak:rak@localhost:5432/rak
PY = backend/.venv/bin/python
PIP = backend/.venv/bin/pip

## One-time DB provisioning (local Postgres must be running)
db:
	psql -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='rak'" | grep -q 1 || psql -d postgres -c "CREATE ROLE rak LOGIN PASSWORD 'rak';"
	psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='rak'" | grep -q 1 || createdb -O rak rak

migrate:
	psql "$(DB_URL)" -v ON_ERROR_STOP=1 -f backend/db/migrations/0001_init.sql
	psql "$(DB_URL)" -v ON_ERROR_STOP=1 -f backend/db/migrations/0002_company_verifications.sql

seed:
	cd backend && .venv/bin/python db/seed/seed.py

venv:
	python3.11 -m venv backend/.venv
	$(PIP) install -U pip
	$(PIP) install -r backend/requirements.txt

## Run servers
backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

## Full setup from scratch
setup: db migrate venv seed
	cd frontend && npm install

## Section 9 acceptance oracle
test:
	cd backend && .venv/bin/python -m pytest tests/test_oracle.py -q

## Reset runtime state (keeps companies/people, clears runs+uploads)
reset:
	psql "$(DB_URL)" -c "update companies set status='not_started'; truncate stage_results, escalations, compliance_runs, lease_records, licenses, passport_verifications, document_uploads, audit_log cascade;"
