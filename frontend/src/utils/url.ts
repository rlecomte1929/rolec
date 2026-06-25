/**
 * URL safety guard for externally-sourced links (AP-02 / SEC-FE-3).
 *
 * Backend/admin-sourced URLs (source_url, pdf_url, document downloads) flow into
 * `href` / `src` / `window.open`. A stored `javascript:` / `data:` / `vbscript:`
 * value would then execute in the app origin (stored-XSS-via-data-field). This
 * allowlists http(s) and relative URLs and rejects every other scheme.
 *
 * Returns the (cleaned) URL when safe, otherwise `fallback` ('#' by default — pass
 * '' for `window.open` so an unsafe URL is falsy and the call is skipped).
 */
export function assertSafeUrl(
  url: string | null | undefined,
  fallback = '#',
): string {
  if (!url) return fallback;
  // Strip control chars browsers ignore, so `java\tscript:` can't slip through.
  const cleaned = url
    .split('')
    .filter((ch) => {
      const code = ch.charCodeAt(0);
      return code > 0x1f && code !== 0x7f;
    })
    .join('')
    .trim();
  if (!cleaned) return fallback;
  const scheme = cleaned.match(/^([a-zA-Z][a-zA-Z0-9+.-]*):/);
  if (scheme) {
    const s = scheme[1].toLowerCase();
    if (s !== 'http' && s !== 'https') return fallback;
  }
  // No scheme → relative path / hash / query / protocol-relative — safe to render.
  return cleaned;
}
