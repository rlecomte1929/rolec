/**
 * statusLabel — AUDIT-A5 (AIQ-358)
 *
 * Single source of truth for mapping backend status enum values to
 * human-readable English strings. Keeps every surface consistent and
 * means we only ever update copy in one place.
 *
 * Design notes:
 * - Flat map: we intentionally avoid a "context" argument so callers
 *   don't have to know the domain. Where the same code means different
 *   things in different domains (e.g. `pending`), we pick the safest
 *   neutral label and let the surrounding UI add context through
 *   headings, columns, or section titles.
 * - i18n-ready: the `locale` argument is reserved for future translation
 *   lookups; for now it is ignored and the function always returns English.
 * - Unknown codes: falls back to a title-cased version of the raw code
 *   so a new backend value never crashes the UI.
 */

// ─── Full mapping ────────────────────────────────────────────────────────────

const STATUS_MAP: Record<string, string> = {
  // ── Immigration readiness (GREEN / AMBER / RED) ─────────────────────────
  GREEN: 'On track',
  AMBER: 'Needs attention',
  RED: 'At risk',

  // ── Quote / RFQ lifecycle ───────────────────────────────────────────────
  fulfilled: 'Quote received',
  acknowledged: 'Acknowledged',

  // ── Claim / invite states (assignment linking) ──────────────────────────
  invite_revoked: 'Invitation cancelled by HR — contact them to reissue',
  expired: 'Invitation expired — ask HR to resend',
  claimed: 'Already accepted',

  // ── General lifecycle ───────────────────────────────────────────────────
  pending: 'Pending',
  active: 'Active',
  inactive: 'Inactive',
  active_for_assistant: 'Active',
  draft: 'Draft',
  approved: 'Approved',
  rejected: 'Not approved',
  submitted: 'Submitted',
  withdrawn: 'Withdrawn',
  escalated: 'Escalated',
  denied: 'Denied',
  countered: 'Counter-offer sent',

  // ── Task / milestone statuses ───────────────────────────────────────────
  not_started: 'Not started',
  in_progress: 'In progress',
  done: 'Done',
  skipped: 'Skipped',
  overdue: 'Overdue',
  blocked: 'Blocked',
  revision_requested: 'Needs revision',

  // ── Case-form statuses ──────────────────────────────────────────────────
  auto_filled: 'Pre-filled',
  pending_doc: 'Waiting for document',
  ready: 'Ready to submit',
  waived: 'Waived',
};

// ─── Public API ──────────────────────────────────────────────────────────────

/**
 * Returns a human-readable label for a backend status enum value.
 *
 * @param code   - The raw status string from the API (e.g. "invite_revoked").
 * @param locale - Reserved for future i18n; currently ignored.
 */
export function statusLabel(code: string, locale?: string): string {
  void locale; // reserved – will wire up when translations land

  if (!code) return '—';

  const mapped = STATUS_MAP[code];
  if (mapped) return mapped;

  // Graceful fallback: title-case the raw value so it's at least readable
  return code
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}
