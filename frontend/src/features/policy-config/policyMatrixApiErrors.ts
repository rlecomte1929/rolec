/**
 * Parse FastAPI 422 detail from policy-config draft PUT / publish validation.
 */

export type ParsedMatrixValidation = {
  /** Human-readable lines for the alert */
  messages: string[];
  /** First server message per benefit_key (field like benefit.mobility_premium) */
  byBenefitKey: Record<string, string>;
  /** effective_date, policy_version, categories, etc. */
  byField: Record<string, string>;
};

export function parsePolicyMatrixValidationDetail(detail: unknown): ParsedMatrixValidation {
  const messages: string[] = [];
  const byBenefitKey: Record<string, string> = {};
  const byField: Record<string, string> = {};

  if (detail == null) {
    return { messages, byBenefitKey, byField };
  }

  if (typeof detail === 'string') {
    messages.push(detail);
    return { messages, byBenefitKey, byField };
  }

  if (typeof detail === 'object' && detail !== null && 'errors' in detail) {
    const raw = (detail as { errors?: unknown }).errors;
    const arr = Array.isArray(raw) ? raw : [];
    for (const item of arr) {
      if (!item || typeof item !== 'object') continue;
      const e = item as { field?: string; message?: string };
      const msg = (e.message || '').trim();
      const field = (e.field || '').trim();
      if (msg) messages.push(field ? `${field}: ${msg}` : msg);
      if (field && msg) {
        byField[field] = msg;
        const bm = /^benefit\.(.+)$/.exec(field);
        if (bm && bm[1]) {
          byBenefitKey[bm[1]] = msg;
        }
      }
    }
    return { messages, byBenefitKey, byField };
  }

  try {
    messages.push(JSON.stringify(detail));
  } catch {
    messages.push('Validation failed.');
  }
  return { messages, byBenefitKey, byField };
}
