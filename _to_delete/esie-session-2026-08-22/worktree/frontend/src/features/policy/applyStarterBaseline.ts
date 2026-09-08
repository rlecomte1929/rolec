/**
 * AIQ-1588: shared starter-baseline seeding for the /hr/policy landing + Policy
 * Builder tab.
 *
 * DECISION (2026-07-19): config-matrix is the canonical subsystem for new-HR
 * baseline seeding — it is what the Policy Builder edits, what test-drive seeds,
 * and what the canonical published read (usePolicyPublished) + over-cap use.
 * Seeding config-matrix keeps seed → edit-in-Builder → publish → employee-compare
 * on ONE subsystem; seeding the legacy company_policies path (the old
 * `initializeFromTemplate`) left the modern Builder showing an empty matrix.
 *
 * The config-matrix apply-template endpoint already accepts the starter card's
 * exact tier keys (conservative | standard | premium), so this is a pure rewire
 * of the two starter-card handlers onto `policyConfigMatrixAPI.hrApplyTemplate`.
 */
import { policyConfigMatrixAPI } from '../../api/client';
import type { StarterTemplateKey } from './starterPolicyCopy';

export type StarterBaselineError = { code?: string; message: string };

/**
 * Seed a config-matrix draft from a starter baseline tier. Throws on failure;
 * callers use {@link parseStarterBaselineError} to surface a readable message
 * (and to detect the 409 `draft_has_rows` case).
 */
export async function applyStarterBaseline(
  key: StarterTemplateKey,
  opts?: { adminCompanyId?: string | null; replaceExistingDraft?: boolean },
): Promise<void> {
  await policyConfigMatrixAPI.hrApplyTemplate(
    { template_key: key, replace_existing_draft: opts?.replaceExistingDraft ?? false },
    opts?.adminCompanyId ?? undefined,
  );
}

/** Normalize an apply-template error into a `{ code, message }` shape. */
export function parseStarterBaselineError(err: unknown): StarterBaselineError {
  const ax = err as {
    response?: { data?: { detail?: { code?: string; message?: string } | string } };
  };
  const detail = ax?.response?.data?.detail;
  const code =
    detail && typeof detail === 'object' && 'code' in detail
      ? (detail as { code?: string }).code
      : undefined;
  const message =
    detail && typeof detail === 'object' && 'message' in detail
      ? String((detail as { message?: string }).message)
      : typeof detail === 'string'
        ? detail
        : 'Could not create baseline policy.';
  return { code, message };
}
