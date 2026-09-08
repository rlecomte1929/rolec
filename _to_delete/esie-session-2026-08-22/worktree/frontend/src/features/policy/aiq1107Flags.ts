/**
 * AIQ-1107 — UX audit (June 2026): hide 8 low-value sections from the HR Policy
 * page to cut cognitive load. Reversible by design (flip to `false`) — the
 * section components are NOT deleted, only gated out of render.
 *
 * Hidden (6 of the 8 audited): More actions, Pre-publish checklist,
 * document-extraction signals (incl. its Document summary), Employee visibility
 * preview, TL;DR, Exclusions & evidence.
 *
 * Deliberately KEPT (the audit listed them but they are core, not clutter):
 *   - "Benefit rules by topic" — this IS the policy benefit matrix.
 *   - "Publish controls" — the fallback publish path (primary publish lives on
 *     the status strip).
 */
export const AIQ1107_HIDE_SECTIONS = true;
