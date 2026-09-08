/**
 * requestLog — a tiny module-level ring buffer of the most recent FAILED API requests,
 * for the feedback diagnostics snapshot (endpoint + status + X-Request-ID correlation id).
 *
 * Kept SEPARATE from client.ts on purpose: client.ts transitively imports api/supabase,
 * which throws "supabaseUrl is required" at module eval under jsdom. Reading the buffer
 * from diagnostics.ts / FeedbackWidget via this lightweight module avoids dragging that
 * whole graph (and the jsdom test trap) into the widget. client.ts only WRITES here.
 */

export interface FailedRequest {
  method: string;
  path: string;
  status: number; // 0 = network error / unreachable
  requestId: string | null;
  ts: string;
}

const MAX_FAILED_REQUESTS = 5;
const recentFailedRequests: FailedRequest[] = [];

export function getRecentFailedRequests(): FailedRequest[] {
  return recentFailedRequests.slice();
}

export function recordFailedRequest(
  method: string,
  path: string,
  status: number,
  requestId: string | null,
): void {
  recentFailedRequests.push({
    method,
    path: path.split('?')[0] || path,
    status,
    requestId,
    ts: new Date().toISOString(),
  });
  if (recentFailedRequests.length > MAX_FAILED_REQUESTS) recentFailedRequests.shift();
}
