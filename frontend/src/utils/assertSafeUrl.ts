/**
 * SEC-FE-3 — guard backend/admin-sourced URLs before they reach href/src/window.open.
 *
 * Returns the URL when it is safe to navigate to (http/https/mailto/tel, or a
 * relative/anchor path), otherwise a safe fallback (default '#'). Rejects the
 * dangerous schemes (`javascript:`, `data:`, `vbscript:`, `file:`) that would
 * otherwise let an attacker-influenceable data field execute script on click —
 * stored-XSS via a URL.
 */
const SAFE_RELATIVE = /^(\/|\.\/|\.\.\/|#|\?)/;
const SAFE_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:']);

export function assertSafeUrl(url: string | null | undefined, fallback = '#'): string {
  if (!url) return fallback;
  const trimmed = url.trim();
  if (!trimmed) return fallback;
  // Relative paths / in-page anchors / query strings are always safe.
  if (SAFE_RELATIVE.test(trimmed)) return trimmed;
  try {
    const base = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
    const parsed = new URL(trimmed, base);
    return SAFE_PROTOCOLS.has(parsed.protocol) ? trimmed : fallback;
  } catch {
    return fallback;
  }
}
