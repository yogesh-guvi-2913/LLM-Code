// API client for the Flash orchestrator. Base is configurable so the dashboard
// can point at any node. In production the dashboard is embedded in and served
// BY the orchestrator, so the default is same-origin; `next dev` (a separate
// server on :3000) falls back to the local orchestrator port.
export const DEFAULT_API = "http://127.0.0.1:8090";

export function apiBase(): string {
  if (typeof window !== "undefined") {
    const fromQuery = new URLSearchParams(window.location.search).get("api");
    if (fromQuery) return fromQuery.replace(/\/$/, "");
    const saved = window.localStorage.getItem("flash_api");
    if (saved) return saved.replace(/\/$/, "");
  }
  if (process.env.NEXT_PUBLIC_API_BASE) {
    return process.env.NEXT_PUBLIC_API_BASE.replace(/\/$/, "");
  }
  // Same origin when served by the orchestrator itself (the native path).
  if (process.env.NODE_ENV === "production" && typeof window !== "undefined") {
    return window.location.origin;
  }
  return DEFAULT_API;
}

export function setApiBase(v: string) {
  if (typeof window !== "undefined") window.localStorage.setItem("flash_api", v.replace(/\/$/, ""));
}

// Operator API key (hyk_…). The control plane requires it on /v1/* when auth is
// enabled. Resolved from ?key=, localStorage, then NEXT_PUBLIC_API_KEY, mirroring
// apiBase(). Distinct from a per-session candidate token (used only for submit).
export function apiKey(): string {
  if (typeof window !== "undefined") {
    const fromQuery = new URLSearchParams(window.location.search).get("key");
    if (fromQuery) return fromQuery;
    const saved = window.localStorage.getItem("flash_api_key");
    if (saved) return saved;
  }
  return process.env.NEXT_PUBLIC_API_KEY || "";
}

export function setApiKey(v: string) {
  if (typeof window !== "undefined") window.localStorage.setItem("flash_api_key", v.trim());
}

// authHeaders attaches the operator key when present, so all reads/writes carry it.
function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...(extra ?? {}) };
  const k = apiKey();
  if (k) h["Authorization"] = `Bearer ${k}`;
  return h;
}

export type TemplateKind = "api" | "frontend";

export interface Template {
  id: string;
  slug: string;
  title: string;
  language: string;
  description: string;
  image: string;
  min_warm: number;
  vcpu: number;
  memory_mb: number;
  pids_limit: number;
  kind: TemplateKind;
  dev_cmd?: string;
  warm: number;
}

// SessionDetail is GET /v1/sessions/{id} — the live URLs are only present while
// the session is ACTIVE.
export interface SessionDetail {
  session_id: string;
  candidate_id: string;
  question_id: string;
  status: SessionStatus;
  expires_at: string;
  session_token?: string;
  app_url?: string;
  preview_url?: string;
  terminal_url?: string;
  terminal_page?: string;
}

export interface CreateSessionInput {
  candidate_id: string;
  question_id: string;
  time_limit_minutes?: number;
}

export interface CreateSessionResult {
  session_id: string;
  session_token: string;
  app_url: string;
  terminal_url: string;
  preview_url?: string;
  expires_at: string;
}

export interface CreateTemplateInput {
  id: string;
  title?: string;
  language?: string;
  description?: string;
  kind: TemplateKind;
  image: string;
  dev_cmd: string;
  min_warm?: number;
  vcpu?: number;
  memory_mb?: number;
  pids_limit?: number;
}

// Usage = GET /v1/usage — the cost proof (billed hours + measured density + $/hr).
export interface Usage {
  billed: {
    sessions: number;
    active_now: number;
    sandbox_hours: number;
    by_question: { question_id: string; sessions: number; active_now: number; sandbox_hours: number }[];
  };
  measured_density: {
    live_containers: number;
    measured_mem_per_sandbox_mb: number;
    configured_mem_per_sandbox_mb: number;
    total_measured_mem_gb: number;
    basis: string;
  };
  cost_model: {
    node_usd_per_hour: number;
    node_ram_gb: number;
    usable_ram_gb: number;
    conservative_sandboxes_per_node: number;
    conservative_usd_per_sandbox_hr: number;
    overcommit_ceiling_sandboxes_per_node: number;
    overcommit_ceiling_usd_per_sandbox_hr: number;
    note: string;
  };
}

// FleetNode = GET /v1/nodes — a sandbox runner (one synthetic node in local mode).
export interface FleetNode {
  id: string;
  host: string;
  addr: string;
  mode: "local" | "cluster";
  mem_total_mb: number;
  mem_free_mb: number;
  active: number;
  warm: Record<string, number>;
  last_seen_unix: number;
}

// AssessmentWindow = an item from GET /v1/windows — a booked pre-warm window. The
// phase is computed server-side from the clock: scheduled → prewarming → active →
// done (or canceled).
export type WindowPhase =
  | "scheduled"
  | "prewarming"
  | "active"
  | "done"
  | "canceled";

export interface AssessmentWindow {
  id: string;
  question_id: string;
  label: string;
  seats: number;
  lead_minutes: number;
  starts_at: string;
  ends_at: string;
  phase: WindowPhase;
}

export interface WindowsResponse {
  windows: AssessmentWindow[];
  desired_warm_now: Record<string, number>;
}

export interface CreateWindowInput {
  question_id: string;
  label?: string;
  seats: number;
  lead_minutes: number;
  starts_at: string; // RFC3339
  ends_at: string; // RFC3339
}

export type SessionStatus = "ACTIVE" | "SUBMITTED" | "TIMED_OUT" | "DESTROYED";

export interface Session {
  id: string;
  candidate_id: string;
  question_id: string;
  status: SessionStatus;
  created_at: string;
  expires_at: string;
  submitted_at?: string;
  score?: number;
  max_score?: number;
  submission_status?: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(apiBase() + path, { cache: "no-store", headers: authHeaders() });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json() as Promise<T>;
}

// sendJSON posts/deletes and surfaces the orchestrator's {error} message on
// failure so callers can show it directly in a toast. When `token` is given (a
// per-session candidate token, e.g. submit) it takes precedence over the operator
// key; otherwise the operator key authenticates the control-plane call.
async function sendJSON<T>(method: string, path: string, body?: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : authHeaders();
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(apiBase() + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `${path} → ${r.status}`;
    try {
      const j = await r.json();
      if (j?.error) msg = j.error;
    } catch {}
    throw new Error(msg);
  }
  if (r.status === 204) return undefined as T;
  const text = await r.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const getTemplates = () => getJSON<Template[]>("/v1/templates");
export const getSessions = () => getJSON<Session[]>("/v1/sessions");
export const getSession = (id: string) => getJSON<SessionDetail>(`/v1/sessions/${id}`);
export const getUsage = () => getJSON<Usage>("/v1/usage");
export const getNodes = () => getJSON<FleetNode[]>("/v1/nodes");

export const scaleTemplate = (id: string, minWarm: number) =>
  sendJSON<{ template: string; min_warm: number }>("POST", `/v1/templates/${id}/min_warm`, {
    min_warm: minWarm,
  });

export const getWindows = (all = false) =>
  getJSON<WindowsResponse>(`/v1/windows${all ? "?all=true" : ""}`);

export const createWindow = (input: CreateWindowInput) =>
  sendJSON<AssessmentWindow>("POST", "/v1/windows", input);

export const cancelWindow = (id: string) =>
  sendJSON<void>("DELETE", `/v1/windows/${id}`);

export const createSession = (input: CreateSessionInput) =>
  sendJSON<CreateSessionResult>("POST", "/v1/sessions", input);

export const createTemplate = (input: CreateTemplateInput) =>
  sendJSON<Template>("POST", "/v1/templates", input);

export const destroySession = (id: string) =>
  sendJSON<void>("DELETE", `/v1/sessions/${id}`);

export const submitSession = (id: string, token: string) =>
  sendJSON<{ submission_id: string; status: string }>(
    "POST",
    `/v1/sessions/${id}/submit`,
    {},
    token,
  );

// ── API keys (operator credential lifecycle) ──

export interface ApiKeyRow {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at?: string;
}

export interface CreatedApiKey {
  id: string;
  name: string;
  prefix: string;
  key: string; // raw key — shown exactly once
}

export const listApiKeys = async () =>
  (await getJSON<{ keys: ApiKeyRow[] }>("/v1/api-keys")).keys ?? [];

export const createApiKey = (name: string) =>
  sendJSON<CreatedApiKey>("POST", "/v1/api-keys", { name });

export const revokeApiKey = (id: string) => sendJSON<void>("DELETE", `/v1/api-keys/${id}`);

// previewSrc / terminalSrc build absolute iframe URLs against the current API
// base (the preview URL the orchestrator returns is already absolute).
export function terminalSrc(detail: SessionDetail): string | undefined {
  return detail.terminal_page ? apiBase() + detail.terminal_page : undefined;
}

// ── Playground (candidate plane) — authorized by the per-session token in the URL,
// not the operator key. This is what an assessment embeds: session + token → IDE.

export interface PlayInfo {
  session_id: string;
  candidate_id: string;
  question_id: string;
  status: SessionStatus;
  kind: TemplateKind;
  title?: string;
  preview_url?: string;
  terminal_page?: string;
  app_url?: string;
}

export interface PlayResult {
  submitted: boolean;
  status?: string;
  score?: number;
  max_score?: number;
}

const tokenQ = (token: string) => `token=${encodeURIComponent(token)}`;

export const getPlayInfo = (id: string, token: string) =>
  getJSON<PlayInfo>(`/v1/sessions/${id}/play?${tokenQ(token)}`);

export const getResult = (id: string, token: string) =>
  getJSON<PlayResult>(`/v1/sessions/${id}/result?${tokenQ(token)}`);

export async function listFiles(id: string, token: string): Promise<string[]> {
  const r = await fetch(`${apiBase()}/v1/sessions/${id}/files?${tokenQ(token)}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`list files → ${r.status}`);
  return (await r.json()).files ?? [];
}

export async function readFile(id: string, token: string, path: string): Promise<string> {
  const r = await fetch(
    `${apiBase()}/v1/sessions/${id}/file?path=${encodeURIComponent(path)}&${tokenQ(token)}`,
    { cache: "no-store" },
  );
  if (!r.ok) throw new Error(`read ${path} → ${r.status}`);
  return r.text();
}

export async function writeFile(id: string, token: string, path: string, content: string): Promise<void> {
  const r = await fetch(
    `${apiBase()}/v1/sessions/${id}/file?path=${encodeURIComponent(path)}&${tokenQ(token)}`,
    { method: "PUT", body: content },
  );
  if (!r.ok) throw new Error(`save ${path} → ${r.status}`);
}

export const playgroundHref = (id: string, token: string) =>
  `/play?session=${encodeURIComponent(id)}&token=${encodeURIComponent(token)}`;
