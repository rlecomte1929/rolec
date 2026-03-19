/**
 * Page load performance instrumentation.
 * Tracks route entry, API requests, shell render, first meaningful content.
 * Disabled unless VITE_PERF_DEBUG=1.
 */

const ENABLED = import.meta.env.VITE_PERF_DEBUG === '1' || import.meta.env.VITE_PERF_DEBUG === 'true';

export interface PagePerfRequestEntry {
  requestName: string;
  endpoint: string;
  route: string;
  caller: string;
  startTs: number;
  endTs?: number;
  durationMs?: number;
  statusCode?: number;
  blockedInitialRender: boolean;
  requestId?: string;
}

export interface PagePerfStage {
  stage: string;
  route: string;
  ts: number;
  durationMs?: number;
  meta?: Record<string, unknown>;
}

const requestEntries: PagePerfRequestEntry[] = [];
const stageEntries: PagePerfStage[] = [];
const MAX_ENTRIES = 150;

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

function log(msg: string, data?: object) {
  if (!ENABLED) return;
  const payload = data ? ` ${JSON.stringify(data)}` : '';
  // eslint-disable-next-line no-console
  console.log(`[page-perf] ${msg}${payload}`);
}

export function trackRouteEntry(route: string): void {
  if (!ENABLED) return;
  const entry: PagePerfStage = { stage: 'route_entry', route, ts: now() };
  stageEntries.push(entry);
  if (stageEntries.length > MAX_ENTRIES) stageEntries.shift();
  log('route_entry', { route });
}

export function trackShellRender(route: string): void {
  if (!ENABLED) return;
  const entry: PagePerfStage = { stage: 'shell_first_render', route, ts: now() };
  stageEntries.push(entry);
  if (stageEntries.length > MAX_ENTRIES) stageEntries.shift();
  log('shell_first_render', { route });
}

export function trackRequestStart(params: {
  requestName: string;
  endpoint: string;
  route: string;
  caller: string;
  blockedInitialRender: boolean;
  requestId?: string;
}): { startTs: number } {
  const startTs = now();
  if (!ENABLED) return { startTs };
  const entry: PagePerfRequestEntry = {
    ...params,
    startTs,
  };
  requestEntries.push(entry);
  if (requestEntries.length > MAX_ENTRIES) requestEntries.shift();
  log('request_start', { ...params });
  return { startTs };
}

export function trackRequestEnd(params: {
  requestName: string;
  endpoint: string;
  route: string;
  startTs: number;
  statusCode?: number;
  requestId?: string;
}): void {
  const endTs = now();
  const durationMs = endTs - params.startTs;
  if (!ENABLED) return;
  const entry = requestEntries.find(
    (e) =>
      e.endpoint === params.endpoint &&
      e.route === params.route &&
      e.startTs === params.startTs &&
      !e.endTs
  );
  if (entry) {
    entry.endTs = endTs;
    entry.durationMs = durationMs;
    entry.statusCode = params.statusCode;
  }
  log('request_end', {
    endpoint: params.endpoint,
    route: params.route,
    durationMs: Math.round(durationMs * 10) / 10,
    statusCode: params.statusCode,
  });
}

export function trackFirstMeaningfulContent(route: string, durationMs?: number): void {
  if (!ENABLED) return;
  stageEntries.push({
    stage: 'first_meaningful_content',
    route,
    ts: now(),
    durationMs,
  });
  if (stageEntries.length > MAX_ENTRIES) stageEntries.shift();
  log('first_meaningful_content', { route, durationMs });
}

export function trackPageInteractive(route: string): void {
  if (!ENABLED) return;
  stageEntries.push({ stage: 'page_interactive', route, ts: now() });
  if (stageEntries.length > MAX_ENTRIES) stageEntries.shift();
  log('page_interactive', { route });
}

export function getPagePerfRequests(): PagePerfRequestEntry[] {
  return requestEntries.slice();
}

export function getPagePerfStages(): PagePerfStage[] {
  return stageEntries.slice();
}
