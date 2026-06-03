import type { HighlightTier } from './types';

/**
 * Color tier → CSS classes. Each tier renders as:
 *   - stroke (border)  — 100% opacity
 *   - fill             — 20% opacity so the underlying PDF text stays legible
 *
 * Colors come from the C1-11D design-token ramps via Tailwind so a
 * single source of truth controls them. If we add tiers later, also
 * extend the legend in the resolution UI.
 */
export const TIER_CLASSES: Record<HighlightTier, { stroke: string; fill: string }> = {
  primary: {
    stroke: 'stroke-primary',
    // Tailwind doesn't have an arbitrary opacity utility for Tailwind v3's
    // dynamic fills, so we route through bg-* + fill-current via a wrapper.
    // Keeping fill on the rect element keeps SVG semantics correct.
    fill: 'fill-[color:var(--rp-color-primary-500)]',
  },
  secondary: {
    stroke: 'stroke-warning',
    fill: 'fill-[color:var(--rp-color-warning-500)]',
  },
  tertiary: {
    stroke: 'stroke-muted-foreground',
    fill: 'fill-[color:var(--rp-color-secondary-500)]',
  },
};

/**
 * Resolved opacity-aware classes for both the resting state and the
 * flash state. We render the rect at 20% fill always; the .animate-
 * bbox-flash utility (defined in src/index.css) layers an opacity
 * animation on top so the bbox briefly pops to full-tier color and
 * fades back.
 */
export function tierToClass(tier: HighlightTier | undefined): { stroke: string; fillClass: string } {
  const resolved = tier ?? 'secondary';
  const { stroke, fill } = TIER_CLASSES[resolved];
  return { stroke, fillClass: fill };
}
