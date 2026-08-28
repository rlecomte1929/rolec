/**
 * Intrinsic dimensions for the static images in `frontend/public/`.
 *
 * Why a lookup rather than literal attributes: the marketing pages render their
 * screenshots through content objects (`platformContent.ts`, `howItWorksContent.ts`,
 * `adLandingContent.ts`, …), so one `<img>` tag serves several different images with
 * different aspect ratios. A hardcoded width/height would be wrong for all but one.
 *
 * Why it matters: without width/height the browser cannot reserve space, so every one of
 * these images shifts the page as it decodes. Only 2 of the 29 `<img>` in this codebase
 * carried dimensions before this. Modern browsers derive `aspect-ratio` from the pair, so
 * the reserved box is correct at any rendered width — the CSS still controls display size.
 *
 * Keep in sync with the files themselves. If you resize one, update it here; the CLS gate
 * (e2e/cls.spec.ts) is what catches a mismatch.
 */
export const PUBLIC_IMAGE_DIMENSIONS: Record<string, { width: number; height: number }> = {
  '/screenshot-hero-case-card.png': { width: 1400, height: 840 },
  '/screenshot-hr-assignments.png': { width: 1024, height: 444 },
  '/screenshot-employee-plan.png': { width: 992, height: 847 },
  '/screenshot-destination-intelligence.png': { width: 1040, height: 669 },
  '/screenshot-provider-recommendations.png': { width: 1040, height: 701 },
  '/screenshot-service-package.png': { width: 660, height: 314 },
  '/relopass-logo.png': { width: 122, height: 128 },
  '/relopass-full-logo.png': { width: 200, height: 300 },
};

/**
 * Spreadable width/height for an `<img src>`. Tolerates the `?v=` cache-busting suffixes
 * that some call sites append, and returns nothing for an unknown/runtime src so callers
 * can use it unconditionally.
 */
export function imgDimensions(src: string | undefined): { width?: number; height?: number } {
  if (!src) return {};
  const [path] = src.split('?');
  return (path ? PUBLIC_IMAGE_DIMENSIONS[path] : undefined) ?? {};
}
