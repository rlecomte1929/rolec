/**
 * Auth/bootstrap performance instrumentation.
 * Use performance.mark()/measure() and structured logs.
 * Disabled in production unless VITE_PERF_DEBUG=1.
 */

const ENABLED = import.meta.env.VITE_PERF_DEBUG === '1' || import.meta.env.VITE_PERF_DEBUG === 'true';

export type AuthPerfStage =
  | 'sign_in_click'
  | 'auth_request_start'
  | 'auth_request_end'
  | 'token_refresh_start'
  | 'token_refresh_end'
  | 'session_fetch_start'
  | 'session_fetch_end'
  | 'route_guard_start'
  | 'route_guard_end'
  | 'bootstrap_start'
  | 'bootstrap_end'
  | 'first_render'
  | 'page_interactive';

export interface AuthPerfEntry {
  stage: AuthPerfStage;
  route?: string;
  durationMs?: number;
  requestId?: string;
  meta?: Record<string, unknown>;
}

const entries: AuthPerfEntry[] = [];
const MAX_ENTRIES = 100;

export function trackAuthPerf(entry: AuthPerfEntry): void {
  if (!ENABLED) return;
  entries.push(entry);
  if (entries.length > MAX_ENTRIES) entries.shift();

  const route = entry.route ? ` route=${entry.route}` : '';
  const dur = entry.durationMs != null ? ` durationMs=${entry.durationMs.toFixed(1)}` : '';
  const rid = entry.requestId ? ` requestId=${entry.requestId}` : '';
  const meta = entry.meta && Object.keys(entry.meta).length
    ? ` ${JSON.stringify(entry.meta)}`
    : '';

  // eslint-disable-next-line no-console
  console.log(`[auth-perf] stage=${entry.stage}${route}${dur}${rid}${meta}`);

  if (typeof performance !== 'undefined' && performance.mark) {
    try {
      performance.mark(`auth-perf-${entry.stage}-${entries.length}`);
    } catch {
      // ignore
    }
  }
}

export function measureAuthSegment(name: string, startMark: string, endMark: string): void {
  if (!ENABLED || typeof performance?.measure !== 'function') return;
  try {
    performance.measure(name, startMark, endMark);
    const measures = performance.getEntriesByName(name, 'measure');
    const m = measures[measures.length - 1];
    if (m?.duration != null) {
      trackAuthPerf({
        stage: 'bootstrap_end',
        durationMs: m.duration,
        meta: { measureName: name },
      });
    }
  } catch {
    // ignore
  }
}

export function getAuthPerfEntries(): AuthPerfEntry[] {
  return entries.slice();
}

export function clearAuthPerfEntries(): void {
  entries.length = 0;
}
