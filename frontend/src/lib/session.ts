/* ─────────────────────────────────────────────────────────────────────────────
 * Client-side session: persists the candidate's one-time access token so
 * authenticated calls (résumé, matches, alerts) survive page reloads.
 *
 * Note: the bearer token lives in localStorage for simplicity. That carries the
 * usual XSS caveat — acceptable for this app; revisit if/when auth hardens.
 * ───────────────────────────────────────────────────────────────────────────── */

const KEY = "jobmatch.session";

export interface Session {
  token: string;
  candidateId: string;
  email?: string;
  resumeId?: string;
}

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function setSession(session: Session): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(session));
}

export function patchSession(partial: Partial<Session>): Session | null {
  const current = getSession();
  if (!current) return null;
  const next = { ...current, ...partial };
  setSession(next);
  return next;
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
}

export function getToken(): string | null {
  return getSession()?.token ?? null;
}
