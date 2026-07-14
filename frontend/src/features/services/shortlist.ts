/**
 * [AIQ-1520] Shortlist shape + hydration.
 *
 * The employee may shortlist SEVERAL vendors per service category — a real RFQ asks three
 * movers for a price and compares them. It used to be one vendor per category.
 *
 * This lives in its own module, apart from ServicesFlowContext, deliberately: the context
 * transitively imports `api/supabase`, whose `createClient` throws under vitest (no
 * VITE_SUPABASE_* in the test env) even though tsc and the build stay green. A pure function
 * should not drag the whole client in just to be tested.
 */

/** category -> the item_ids the employee shortlisted for it. Never an empty array. */
export type Shortlist = Map<string, string[]>;

/**
 * Hydrate the shortlist from either stored shape.
 *
 * The stored shape — in localStorage (`services_shortlist`) AND inside the server-side
 * `services_state` blob — was `[category, item_id][]`. It is now `[category, item_id[]][]`.
 * Real users have the old one on disk right now, so hydration must accept both:
 *
 *   legacy  ["movers", "m-2"]          -> ["m-2"]
 *   new     ["movers", ["m-2", "m-4"]] -> passes through (idempotent)
 *   junk                                -> skipped, never throws
 *
 * Empty arrays are PRUNED: `ServicesEstimate` gates its "Request quotations" CTA on
 * `shortlist.size > 0`, so a category left as `[]` after de-selecting its last vendor would
 * falsely enable it.
 */
export const toShortlistMap = (raw: unknown): Shortlist => {
  const map: Shortlist = new Map();
  if (!Array.isArray(raw)) return map;
  for (const entry of raw) {
    if (!Array.isArray(entry) || entry.length < 2) continue;
    const [category, value] = entry as [unknown, unknown];
    if (typeof category !== 'string' || !category) continue;
    const ids = (Array.isArray(value) ? value : [value]).filter(
      (v): v is string => typeof v === 'string' && v.length > 0,
    );
    if (ids.length) map.set(category, ids);
  }
  return map;
};
