/* Lightweight performance instrumentation utilities for frontend.
 *
 * - Tracks per-request timings keyed by requestId (X-Request-ID).
 * - Tracks interactions (click -> UI update) keyed by interaction id.
 * - No external deps; dev-focused and enabled via VITE_PERF_DEBUG.
 */

type RequestMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'OPTIONS' | 'HEAD' | string;

export interface RequestPerfEntry {
  requestId: string;
  method: RequestMethod;
  path: string;
  status: number;
  ok: boolean;
  durationHeadersMs: number;
  durationBodyMs: number;
  startedAt: number;
}

export interface InteractionHandle {
  id: string;
  name: string;
  t0: number;
}

export interface InteractionPerfEntry {
  id: string;
  name: string;
  clickToRenderMs: number;
  startedAt: number;
  finishedAt: number;
  requestCount: number;
}

const MAX_REQUEST_LOGS = 200;
const MAX_INTERACTIONS = 50;

const requestLog: RequestPerfEntry[] = [];
const interactions: InteractionPerfEntry[] = [];

type Listener = () => void;
const listeners = new Set<Listener>();

let currentInteractionId: string | null = null;

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

const genId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    // @ts-expect-error: randomUUID exists in modern browsers
    return crypto.randomUUID() as string;
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
};

function notifyListeners() {
  if (!listeners.size) return;
  for (const fn of listeners) {
    try {
      fn();
    } catch {
      // swallow
    }
  }
}

export function recordRequestPerf(entry: RequestPerfEntry) {
  requestLog.push(entry);
  if (requestLog.length > MAX_REQUEST_LOGS) {
    requestLog.splice(0, requestLog.length - MAX_REQUEST_LOGS);
  }
  // Console log for quick inspection
  // Example: [perf] req <id> GET /api/foo status=200 headers_ms=12.3 body_ms=20.1
  // eslint-disable-next-line no-console
  console.log(
    `[perf] req ${entry.requestId} ${entry.method} ${entry.path} ` +
      `status=${entry.status} ok=${entry.ok} ` +
      `headers_ms=${entry.durationHeadersMs.toFixed(1)} body_ms=${entry.durationBodyMs.toFixed(1)}`
  );
  notifyListeners();
}

export function getRequestLog(): RequestPerfEntry[] {
  return requestLog.slice();
}

export function getCurrentInteractionId(): string | null {
  return currentInteractionId;
}

export function startInteraction(name: string): InteractionHandle {
  const id = genId();
  const t0 = now();
  currentInteractionId = id;
  return { id, name, t0 };
}

export async function endInteraction(handle: InteractionHandle): Promise<void> {
  // Wait for next paint to approximate "UI updated"
  const tRender = await new Promise<number>((resolve) => {
    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame(() => resolve(now()));
    } else {
      resolve(now());
    }
  });

  const clickToRenderMs = tRender - handle.t0;
  const reqsForInteraction = requestLog.filter((r) => r.requestId === handle.id);

  const entry: InteractionPerfEntry = {
    id: handle.id,
    name: handle.name,
    clickToRenderMs,
    startedAt: handle.t0,
    finishedAt: tRender,
    requestCount: reqsForInteraction.length,
  };

  interactions.push(entry);
  if (interactions.length > MAX_INTERACTIONS) {
    interactions.splice(0, interactions.length - MAX_INTERACTIONS);
  }

  // eslint-disable-next-line no-console
  console.log(
    `[perf] interaction ${handle.name} id=${handle.id} ` +
      `click_to_render_ms=${clickToRenderMs.toFixed(1)} requests=${entry.requestCount}`
  );

  // Clear current interaction if it matches
  if (currentInteractionId === handle.id) {
    currentInteractionId = null;
  }

  notifyListeners();
}

export function getRecentInteractions(limit = 10): InteractionPerfEntry[] {
  if (!interactions.length) return [];
  return interactions.slice(-limit).reverse();
}

export function subscribePerf(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

