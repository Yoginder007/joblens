/* Small presentational helpers shared by job cards and detail panes. */

/** Stable hash → hue, so each company always gets the same avatar gradient. */
function hashHue(text: string): number {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}

/** CSS gradient for a company "logo" avatar, deterministic per name. */
export function companyGradient(name: string): string {
  const hue = hashHue(name || "?");
  return `linear-gradient(135deg, hsl(${hue} 70% 52%), hsl(${(hue + 48) % 360} 72% 44%))`;
}

/** Up-to-two-letter initials for the avatar (e.g. "Goldman Sachs" → "GS"). */
export function companyInitials(name: string): string {
  const words = (name || "?").trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return (words[0] || "?").slice(0, 2).toUpperCase();
}

// Company names whose brand domain isn't a clean slug of the name.
const DOMAIN_OVERRIDES: Record<string, string> = {
  "cred": "cred.club",
  "d.e. shaw & co.": "deshaw.com",
  "d.e. shaw": "deshaw.com",
  "goldman sachs": "goldmansachs.com",
};

/** Best-effort brand domain for a company name → used to fetch a real favicon
 *  (with a gradient-initials fallback when none resolves). */
export function companyDomain(name: string): string | null {
  const key = (name || "").trim().toLowerCase();
  if (!key) return null;
  if (DOMAIN_OVERRIDES[key]) return DOMAIN_OVERRIDES[key];
  // Strip legal suffixes + punctuation, collapse spaces → "<slug>.com".
  const slug = key
    .replace(/\b(inc|llc|ltd|corp|co|company|technologies|labs)\b/g, "")
    .replace(/[^a-z0-9]/g, "");
  return slug ? `${slug}.com` : null;
}

/** Real-favicon URL for a domain (Google's service — free, no key, reliable). */
export function faviconUrl(domain: string, size = 64): string {
  return `https://www.google.com/s2/favicons?domain=${domain}&sz=${size}`;
}

/** Human freshness label from an ISO date ("today", "3d ago", "2mo ago"). */
export function daysAgo(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}
