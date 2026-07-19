// SNAPSHOT (2026-07-18) of lib/pricing.ts — the live workspace file is authoritative.

/**
 * ReloPass pricing constants — Case Command paid tiers.
 *
 * The AUTHORITATIVE amounts live server-side in the `case-checkout` server
 * function (the client never sends an amount to Stripe). These constants are
 * the display-side mirror: keep them in sync with the hook when pricing
 * changes.
 *
 * NOTE (platform reality): Audos spaces have no .env file and the platform
 * Stripe integration prices sessions by amount-in-cents, not by Stripe price
 * IDs — so the spec's STRIPE_PRICE_ROADMAP / STRIPE_PRICE_ESSENTIALS env vars
 * are represented here as cent amounts instead. STRIPE_SECRET_KEY and
 * STRIPE_WEBHOOK_SECRET are managed by the platform and never touch this
 * codebase.
 */

/** Tier 1 — full roadmap + vendor shortlist unlock. €800 one-time. */
export const PRICE_ROADMAP_CENTS = 80000;

/** Tier 2 — Immigration assurance (Essentials). €2,000 one-time. SCAFFOLD ONLY — not wired to checkout in v0. */
export const PRICE_ESSENTIALS_CENTS = 200000;

export const PRICING_CURRENCY = 'EUR';

export type AccessTier = 'free' | 'roadmap' | 'essentials';
export type PaymentStatus = 'unpaid' | 'pending' | 'paid' | 'refunded';

/** Tier ordering for access checks: does `tier` grant at least `required`? */
const TIER_RANK: Record<AccessTier, number> = { free: 0, roadmap: 1, essentials: 2 };

export function tierAtLeast(tier: string | null | undefined, required: AccessTier): boolean {
  const rank = TIER_RANK[(tier as AccessTier) || 'free'] ?? 0;
  return rank >= TIER_RANK[required];
}

export function formatEur(cents: number): string {
  const whole = cents / 100;
  return `€${Number.isInteger(whole) ? whole.toLocaleString('en-GB') : whole.toFixed(2)}`;
}
