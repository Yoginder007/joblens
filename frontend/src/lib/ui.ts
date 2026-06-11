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
