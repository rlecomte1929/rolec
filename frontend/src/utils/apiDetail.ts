/**
 * Normalize FastAPI/axios `detail` payloads (string | { code, message } | validation array).
 */
export function getApiErrorMessage(err: unknown, fallback = ''): string {
  const ax = err as { response?: { data?: { detail?: unknown } } };
  const detail = ax?.response?.data?.detail;
  return formatDetailToString(detail, fallback);
}

export function formatDetailToString(detail: unknown, fallback = ''): string {
  if (detail == null || detail === '') return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    if (first?.msg) return String(first.msg);
    return fallback || 'Request failed.';
  }
  if (typeof detail === 'object') {
    const o = detail as { message?: string; msg?: string };
    if (o.message) return String(o.message);
    if (o.msg) return String(o.msg);
  }
  return fallback || String(detail);
}

export function getApiErrorCode(err: unknown): string | undefined {
  const ax = err as { response?: { data?: { detail?: unknown } } };
  const detail = ax?.response?.data?.detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const c = (detail as { code?: string }).code;
    return typeof c === 'string' ? c : undefined;
  }
  return undefined;
}
