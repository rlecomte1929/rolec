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

/**
 * User-facing hint when axios has no HTTP response (timeout, CORS block, DNS, offline).
 * Browsers often surface CORS failures as "Network Error" with status 0.
 */
export function getClientTransportErrorMessage(err: unknown): string | undefined {
  const e = err as {
    code?: string;
    message?: string;
    response?: { status?: number };
  };
  if (e?.code === 'ECONNABORTED') {
    return 'Request timed out. The API may be cold-starting or overloaded — wait a moment and try again.';
  }
  if (!e?.response && typeof e?.message === 'string' && /network error/i.test(e.message)) {
    return (
      'Cannot reach the API (network or CORS). In production, confirm https://api.relopass.com/health ' +
      'and that the API allows Origin https://relopass.com (see docs/PRODUCTION_RELIABILITY.md).'
    );
  }
  return undefined;
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
