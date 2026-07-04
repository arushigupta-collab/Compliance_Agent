import axios from "axios";

const api = axios.create({ baseURL: "/api/v1" });

// ---- Types (mirror backend domain models) ----
export interface Company {
  id: string;
  sr: string;
  name: string;
  archetype: "individual" | "corporate" | "dao";
  company_type: string;
  activity: string;
  activity_class: string;
  risk_tier: string;
  jurisdiction?: string;
  package: string;
  visa_quota: number;
  premium: boolean;
  token_issuing: boolean;
  preapproval_status?: string | null;
  status: string;
  attributes: Record<string, any>;
}

export interface Person {
  id: string;
  company_id: string;
  name: string;
  role: string;
  nationality?: string;
  dob?: string;
  passport_no?: string;
  passport_expiry?: string;
  poa_date?: string;
  ubo_pct?: string;
  is_ubo: boolean;
  is_signatory: boolean;
}

export interface ChecklistRow {
  doc_key: string;
  label: string;
  source: "generated" | "uploaded";
  required: boolean;
  status: "missing" | "uploaded" | "extracted";
  filename?: string;
  extracted_fields: Record<string, any>;
}

export interface PassportVerification {
  id?: string;
  company_id: string;
  person_id: string;
  person_name?: string;
  face_match_score?: number;
  checks: Record<string, any>;
  overall?: "verified" | "flagged";
}

export interface CompanyProfile {
  company: Company;
  people: Person[];
  checklist: ChecklistRow[];
  passport_verifications: PassportVerification[];
  can_run: boolean;
  run_blockers: string[];
}

export interface StageResult {
  stage: string;
  decision: string;
  risk_score?: number;
  exceptions: any[];
  detail?: Record<string, any>;
}

export interface Escalation {
  id?: string;
  level: string;
  status: string;
  decided_by?: string;
}

export interface RunSummary {
  run_id: string;
  company_id: string;
  status: string;
  stages: StageResult[];
  escalations: Escalation[];
}

export interface LeaseRecord {
  package?: string;
  term?: string;
  visa_quota?: number;
  fee?: string;
  crm_ref?: string;
  status: string;
}

export interface License {
  cert_no?: string;
  license_no?: string;
  establishment_card_no?: string;
  documents_visible: boolean;
  issued_at?: string;
}

export interface AuditEntry {
  id: string;
  actor?: string;
  action: string;
  payload: Record<string, any>;
  created_at: string;
}

export interface SchemaHealth {
  ok: boolean;
  missing_views: string[];
  missing_fields: string[];
}

// ---- API calls ----
export const getCompanies = () => api.get<Company[]>("/companies").then((r) => r.data);
export const getProfile = (sr: string) => api.get<CompanyProfile>(`/companies/${sr}`).then((r) => r.data);
export const getSchemaHealth = () => api.get<SchemaHealth>("/health/schema").then((r) => r.data);

export const uploadDocument = (sr: string, form: FormData) =>
  api.post(`/companies/${sr}/documents`, form).then((r) => r.data);

export const loadSeedDocuments = (sr: string) =>
  api.post<{ loaded: number; doc_keys: string[] }>(`/companies/${sr}/load-seed-documents`).then((r) => r.data);

export const verifyPassport = (sr: string, form: FormData) =>
  api.post<PassportVerification>(`/companies/${sr}/passport-verifications`, form).then((r) => r.data);

export const startRun = (sr: string) =>
  api.post<{ run_id: string }>(`/companies/${sr}/runs`).then((r) => r.data);

export const getRun = (runId: string) => api.get<RunSummary>(`/runs/${runId}`).then((r) => r.data);

export const decideEscalation = (runId: string, level: string, status: string) =>
  api.post(`/runs/${runId}/escalations/${level}`, { status }).then((r) => r.data);

export const getLease = (sr: string) => api.get<LeaseRecord | null>(`/companies/${sr}/lease`).then((r) => r.data);
export const getLicense = (sr: string) => api.get<License | null>(`/companies/${sr}/license`).then((r) => r.data);
export const getAudit = (sr: string) => api.get<AuditEntry[]>(`/companies/${sr}/audit`).then((r) => r.data);

export const runStreamUrl = (runId: string) => `/api/v1/runs/${runId}/stream`;
export const stageStreamUrl = (runId: string, stage: string) =>
  `/api/v1/runs/${runId}/stages/${stage}/stream`;
export default api;
