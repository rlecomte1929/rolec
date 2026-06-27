// Humanize an intake-submit failure (AIQ-1311). The submit endpoint returns a
// structured 400 — `{ message, missingFields, suggestedStep }` — but axios wraps
// it so the bare `.message` is "Request failed with status code 400". This pulls
// the real message and the step to jump back to, from either an axios error
// (`response.data.detail`) or a fetch/buildApiError error (`err.detail`), and
// never leaks the raw axios string to the user.

export interface ParsedSubmitError {
  message: string;
  /** 1-based wizard step to return the user to, when the API pinpoints one. */
  suggestedStep: number | null;
}

const GENERIC = 'Submission failed. Please try again.';

export function parseSubmitError(e: unknown): ParsedSubmitError {
  const err = e as {
    message?: string;
    detail?: unknown;
    response?: { data?: { detail?: unknown } };
  } | null | undefined;

  const detail = err?.detail ?? err?.response?.data?.detail;

  if (detail && typeof detail === 'object') {
    const d = detail as { message?: string; suggestedStep?: number };
    return {
      message: d.message || GENERIC,
      suggestedStep: typeof d.suggestedStep === 'number' ? d.suggestedStep : null,
    };
  }

  if (typeof detail === 'string' && detail.trim()) {
    return { message: detail, suggestedStep: null };
  }

  // A meaningful client-side message (e.g. the save-failed precondition) is fine
  // to show; the bare axios "Request failed with status code N" is not.
  const raw = err?.message;
  if (raw && !/request failed with status code/i.test(raw)) {
    return { message: raw, suggestedStep: null };
  }

  return { message: GENERIC, suggestedStep: null };
}
