/* ─────────────────────────────────────────────────────────────────────────────
 * API Service Layer — all communication with the FastAPI backend (v2).
 *
 * Auth model: POST /api/candidates returns a one-time bearer token; résumé,
 * match, and subscription endpoints require `Authorization: Bearer <token>`.
 * ───────────────────────────────────────────────────────────────────────────── */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

async function parseError(res: Response, fallback: string): Promise<never> {
  const err = await res.json().catch(() => ({}));
  throw new Error((err as { detail?: string }).detail || `${fallback} (${res.status})`);
}

/* ── Client-side GET cache + in-flight dedupe ──────────────────────────────────
 * Public, idempotent GETs (job search, filter options, boards…) are cached in
 * memory with a short TTL and deduped while in flight. This is what makes tab
 * switches feel instant: returning to Browse after the Match flow no longer
 * re-fetches page 0 + facets, and the filter-option catalogue (requested by both
 * the match and browse filter UIs) is fetched once and shared. Authenticated /
 * mutating endpoints deliberately bypass this. */
interface CacheEntry<T> {
  value: T;
  expires: number;
}
const _cache = new Map<string, CacheEntry<unknown>>();
const _inflight = new Map<string, Promise<unknown>>();
// Bounded: distinct search-param combos accumulate over a long session.
const _CACHE_MAX_ENTRIES = 80;

async function cachedGet<T>(key: string, ttlMs: number, fetcher: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const hit = _cache.get(key) as CacheEntry<T> | undefined;
  if (hit && hit.expires > now) return hit.value;

  const flying = _inflight.get(key) as Promise<T> | undefined;
  if (flying) return flying;

  const p = fetcher()
    .then((value) => {
      if (_cache.size >= _CACHE_MAX_ENTRIES) {
        // Map preserves insertion order — drop the oldest entry.
        const oldest = _cache.keys().next().value;
        if (oldest !== undefined) _cache.delete(oldest);
      }
      _cache.set(key, { value, expires: Date.now() + ttlMs });
      return value;
    })
    .finally(() => {
      _inflight.delete(key);
    });
  _inflight.set(key, p);
  return p;
}

/* ── Cold-start-aware fetch for public GETs ────────────────────────────────────
 * The free-tier backend sleeps when idle; the first requests of a session hit
 * a server that's still booting (network errors / 502-504 from the proxy).
 * Retrying idempotent GETs with backoff means content pops in by itself the
 * moment the backend wakes — no manual refresh. Mutating/authenticated calls
 * deliberately do NOT retry (they run after the app is interactive). */
const _RETRYABLE_STATUS = new Set([502, 503, 504]);

async function publicFetch(url: string, retryForMs = 90_000): Promise<Response> {
  const deadline = Date.now() + retryForMs;
  let delay = 1_500;
  for (;;) {
    let res: Response | null = null;
    try {
      res = await fetch(url);
    } catch {
      res = null; // network error — offline or cold start
    }
    if (res && !_RETRYABLE_STATUS.has(res.status)) return res;
    if (Date.now() + delay >= deadline) {
      if (res) return res;
      throw new Error("Server unreachable — it may still be waking up. Please retry in a moment.");
    }
    await new Promise((r) => setTimeout(r, delay));
    delay = Math.min(delay * 1.7, 8_000);
  }
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface Candidate {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface CandidateCreated extends Candidate {
  access_token: string;
}

export interface ResumeUpload {
  id: string;
  candidate_id: string;
  file_name: string;
  status: string;
  created_at: string;
}

export interface ResumeDetail {
  id: string;
  candidate_id: string;
  file_name: string;
  status: "pending" | "processing" | "embedding" | "ready" | "failed";
  parsed_data: {
    full_name?: string;
    current_title?: string;
    total_years_experience?: number;
    technical_skills?: Array<{ category?: string; skills: string[] } | string>;
  } | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobBoard {
  id: string;
  name: string;
  label: string;
  logo_url: string | null;
  category: string;
  is_premium: boolean;
  is_active: boolean;
}

export interface MatchedSkill {
  skill: string;
  found_in_resume: boolean;
  required: boolean;
}

export interface EligibleJob {
  job_id: string;
  title: string;
  company: string;
  description: string | null;
  source: string | null;
  location: string | null;
  required_experience_years: number;
  technical_skills: string[] | null;
  job_url: string | null;
  match_score: number;
  reasoning: string;
  semantic_similarity: number;
  skill_match_percentage: number;
  matched_skills: MatchedSkill[];
  work_model: string | null;
  industry: string | null;
  job_type: string | null;
  role_category: string | null;
}

export interface EligibleJobsResponse {
  resume_id: string;
  candidate_experience_years: number;
  total_eligible: number;
  eligible_jobs: EligibleJob[];
}

export interface JobMatchResult {
  job: RecentJob;
  match_score: number;
  hard_filter_passed: boolean;
  semantic_similarity: number | null;
  skill_match_percentage: number | null;
  matched_skills: MatchedSkill[];
  reasoning: string;
}

export interface CompanyMatchGroup {
  company_name: string;
  jobs: JobMatchResult[];
}

export interface MatchesResponse {
  resume_id: string;
  total_matches: number;
  companies: CompanyMatchGroup[];
  matches: JobMatchResult[];
}

export interface SearchFilters {
  location?: string;
  title_keyword?: string;
  experience_min?: number;
  max_experience?: number;
  work_model?: string;
  job_type?: string;
  roles?: string[];
  posted_within_days?: number;
  sources?: string[];
  match_mode?: "semantic" | "direct";
}

export interface FacetCounts {
  work_model: Record<string, number>;
  experience_ranges: Record<string, number>;
  industries: Record<string, number>;
  job_types: Record<string, number>;
  posted_within: Record<string, number>;
  sources: Record<string, number>;
  roles: Record<string, number>;
}

export interface RecentJob {
  id: string;
  title: string;
  company: string;
  description: string;
  required_experience_years: number;
  technical_skills: string[] | null;
  salary_min: number | null;
  salary_max: number | null;
  location: string | null;
  job_url: string | null;
  source: string;
  source_id: string;
  posted_date: string | null;
  scraped_at: string | null;
  is_active: boolean;
  is_remote?: boolean;
  work_model?: string | null;
  industry?: string | null;
  company_rating?: number | null;
  company_size?: string | null;
  job_type?: string | null;
  role_category?: string | null;
}

export interface SearchV2Response {
  total: number;
  jobs: RecentJob[];
  facets: FacetCounts | null;
}

export interface SearchV2Filters {
  q?: string;
  location?: string;
  work_model?: string;
  salary_min?: number;
  salary_max?: number;
  experience_min?: number;
  experience_max?: number;
  posted_within_days?: number;
  industry?: string;
  job_type?: string;
  roles?: string[];
  sources?: string[];
  companies?: string[];
  sort_by?: "relevance" | "date" | "salary";
  include_facets?: boolean;
  limit?: number;
  offset?: number;
}

export interface Subscription {
  id: string;
  resume_id: string;
  filters: Record<string, unknown>;
  min_score: number;
  frequency: string;
  channel: string;
  destination: string | null;
  is_active: boolean;
  last_run_at: string | null;
  created_at: string;
}

export interface SubscriptionCreate {
  resume_id: string;
  filters?: {
    location?: string;
    title_keyword?: string;
    work_model?: string;
    sources?: string[];
  };
  min_score?: number;
  frequency?: "instant" | "daily" | "weekly";
  channel?: "email" | "webhook";
  destination?: string;
}

// ── Candidates ─────────────────────────────────────────────────────────────

export async function createCandidate(
  email: string,
  fullName: string
): Promise<CandidateCreated> {
  const res = await fetch(`${API_BASE}/api/candidates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name: fullName }),
  });
  if (!res.ok) await parseError(res, "Failed to create candidate");
  return res.json();
}

// ── Account auth (email + password) ──────────────────────────────────────────

export async function signup(
  email: string,
  fullName: string,
  password: string
): Promise<CandidateCreated> {
  const res = await fetch(`${API_BASE}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name: fullName, password }),
  });
  if (!res.ok) await parseError(res, "Sign up failed");
  return res.json();
}

export async function login(email: string, password: string): Promise<CandidateCreated> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) await parseError(res, "Login failed");
  return res.json();
}

// ── Résumés (authenticated) ──────────────────────────────────────────────────

export async function uploadResume(token: string, file: File): Promise<ResumeUpload> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/resumes/upload`, {
    method: "POST",
    headers: authHeaders(token), // do NOT set Content-Type — browser adds the multipart boundary
    body: formData,
  });
  if (!res.ok) await parseError(res, "Failed to upload resume");
  return res.json();
}

export async function getResumeStatus(token: string, resumeId: string): Promise<ResumeDetail> {
  const res = await fetch(`${API_BASE}/api/resumes/${resumeId}`, { headers: authHeaders(token) });
  if (!res.ok) await parseError(res, "Failed to get resume status");
  return res.json();
}

export async function pollResumeUntilReady(
  token: string,
  resumeId: string,
  onProgress?: (status: string) => void,
  // Matches the backend's ~3 min processing window (slow LLM parses on the
  // free tier must not be reported as failures at 40s).
  maxAttempts = 180
): Promise<ResumeDetail> {
  for (let i = 0; i < maxAttempts; i++) {
    const detail = await getResumeStatus(token, resumeId);
    onProgress?.(detail.status);
    if (detail.status === "ready") return detail;
    if (detail.status === "failed") throw new Error("Resume processing failed");
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("Timeout waiting for resume processing");
}

/**
 * Stream résumé status via Server-Sent Events (one connection instead of N
 * polls). The token rides as a query param because EventSource can't set
 * headers. Any stream error falls back to {@link pollResumeUntilReady}.
 */
export function streamResumeUntilReady(
  token: string,
  resumeId: string,
  onProgress?: (status: string) => void
): Promise<ResumeDetail> {
  return new Promise((resolve, reject) => {
    if (typeof EventSource === "undefined") {
      pollResumeUntilReady(token, resumeId, onProgress).then(resolve, reject);
      return;
    }
    const url = `${API_BASE}/api/resumes/${resumeId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    let settled = false;
    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      es.close();
      fn();
    };

    es.onmessage = (e) => {
      let status: string;
      try {
        status = (JSON.parse(e.data) as { status: string }).status;
      } catch {
        return;
      }
      onProgress?.(status);
      if (status === "ready") finish(() => getResumeStatus(token, resumeId).then(resolve, reject));
      else if (status === "failed") finish(() => reject(new Error("Resume processing failed")));
    };

    // Stream unsupported/blocked or closed early → fall back to polling.
    es.onerror = () => finish(() => pollResumeUntilReady(token, resumeId, onProgress).then(resolve, reject));
  });
}

// ── Matching (authenticated) ─────────────────────────────────────────────────

export async function getEligibleJobs(
  token: string,
  resumeId: string,
  filters: SearchFilters
): Promise<EligibleJobsResponse> {
  const params = new URLSearchParams({ resume_id: resumeId });
  if (filters.location) params.set("location", filters.location);
  if (filters.title_keyword) params.set("title_keyword", filters.title_keyword);
  if (filters.experience_min !== undefined) params.set("experience_min", String(filters.experience_min));
  if (filters.max_experience !== undefined) params.set("max_experience", String(filters.max_experience));
  if (filters.work_model) params.set("work_model", filters.work_model);
  if (filters.job_type) params.set("job_type", filters.job_type);
  if (filters.roles?.length) params.set("roles", filters.roles.join(","));
  if (filters.posted_within_days !== undefined) params.set("posted_within_days", String(filters.posted_within_days));
  if (filters.sources?.length) params.set("sources", filters.sources.join(","));
  if (filters.match_mode) params.set("match_mode", filters.match_mode);

  const res = await fetch(`${API_BASE}/api/jobs/eligible?${params}`, { headers: authHeaders(token) });
  if (!res.ok) await parseError(res, "Failed to get eligible jobs");
  return res.json();
}

export async function getJobMatches(
  token: string,
  resumeId: string,
  opts: { min_score?: number; limit?: number } = {}
): Promise<MatchesResponse> {
  const params = new URLSearchParams({
    resume_id: resumeId,
    min_score: String(opts.min_score ?? 0),
    limit: String(opts.limit ?? 50),
  });
  const res = await fetch(`${API_BASE}/api/jobs/matches?${params}`, { headers: authHeaders(token) });
  if (!res.ok) await parseError(res, "Failed to get matches");
  return res.json();
}

// ── Browse (public) ──────────────────────────────────────────────────────────

export async function getBoards(): Promise<JobBoard[]> {
  return cachedGet("boards", 300_000, async () => {
    const res = await publicFetch(`${API_BASE}/api/boards`);
    if (!res.ok) throw new Error(`Failed to fetch boards (${res.status})`);
    return res.json();
  });
}

export interface Portal {
  company: string;
  careers_url: string;
  live: boolean;
  ats: string;
  group: "india" | "global" | "aggregator";
}

export async function getPortals(): Promise<Portal[]> {
  return cachedGet("portals", 300_000, async () => {
    const res = await publicFetch(`${API_BASE}/api/portals`);
    if (!res.ok) throw new Error(`Failed to fetch portals (${res.status})`);
    return res.json();
  });
}

export interface FilterOptions {
  locations: string[];
  countries: string[];
  industries: string[];
  titles: string[];
  companies: string[];
  sources: string[];
  work_models: string[];
  job_types: string[];
  roles: string[];
}

export async function getFilterOptions(): Promise<FilterOptions> {
  // The catalogue changes only when ingestion runs, and both the match and
  // browse filter UIs request it — cache it for several minutes and share it.
  return cachedGet("filter-options", 300_000, async () => {
    const res = await publicFetch(`${API_BASE}/api/jobs/options`);
    if (!res.ok) throw new Error(`Failed to fetch filter options (${res.status})`);
    return res.json();
  });
}

export async function searchJobs(filters: SearchV2Filters): Promise<SearchV2Response> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, Array.isArray(value) ? value.join(",") : String(value));
    }
  }
  // Short TTL: results stay fresh but identical queries within a browsing
  // session (esp. paging back/forth and re-entering the Browse tab) are instant.
  return cachedGet(`search:${params}`, 60_000, async () => {
    const res = await publicFetch(`${API_BASE}/api/jobs/search?${params}`);
    if (!res.ok) await parseError(res, "Failed to search jobs");
    return res.json();
  });
}

// ── Subscriptions / Job Alerts (authenticated) ───────────────────────────────

export async function createSubscription(
  token: string,
  payload: SubscriptionCreate
): Promise<Subscription> {
  const res = await fetch(`${API_BASE}/api/subscriptions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await parseError(res, "Failed to create alert");
  return res.json();
}

export async function listSubscriptions(token: string): Promise<Subscription[]> {
  const res = await fetch(`${API_BASE}/api/subscriptions`, { headers: authHeaders(token) });
  if (!res.ok) await parseError(res, "Failed to load alerts");
  return res.json();
}

export async function deleteSubscription(token: string, id: string): Promise<Subscription> {
  const res = await fetch(`${API_BASE}/api/subscriptions/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) await parseError(res, "Failed to delete alert");
  return res.json();
}
