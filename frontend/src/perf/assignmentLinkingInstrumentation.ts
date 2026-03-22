/**
 * Structured logs for employee assignment linking / overview verification.
 *
 * Enable: `VITE_ASSIGNMENT_FLOW_LOG=1` (or `true`), or any dev build (`import.meta.env.DEV`).
 * Log prefix: `[assignment-flow]` — safe to grep in browser devtools or E2E artifacts.
 *
 * Server-side counterparts use `identity_obs` JSON lines (see `backend/identity_observability.py`).
 */

const enabled = () =>
  import.meta.env.DEV ||
  import.meta.env.VITE_ASSIGNMENT_FLOW_LOG === '1' ||
  import.meta.env.VITE_ASSIGNMENT_FLOW_LOG === 'true';

const MAX_BUFFER = 200;
const buffer: Array<{ t: number; event: string; detail?: Record<string, unknown> }> = [];

export const ASSIGNMENT_FLOW_EVENTS = {
  overviewLookupStart: 'assignment_flow.overview_lookup_start',
  overviewLookupComplete: 'assignment_flow.overview_lookup_complete',
  postLoginRoute: 'assignment_flow.post_login_route',
  hubResolution: 'assignment_flow.hub_resolution',
  linkPendingAttempt: 'assignment_flow.link_pending_attempt',
  linkPendingComplete: 'assignment_flow.link_pending_complete',
  manualClaimAttempt: 'assignment_flow.manual_claim_attempt',
  manualClaimClientValidationFailed: 'assignment_flow.manual_claim_client_validation_failed',
  manualClaimComplete: 'assignment_flow.manual_claim_complete',
} as const;

export function trackAssignmentFlow(event: string, detail?: Record<string, unknown>): void {
  if (!enabled()) return;
  const row = { t: typeof performance !== 'undefined' ? performance.now() : Date.now(), event, detail };
  buffer.push(row);
  if (buffer.length > MAX_BUFFER) buffer.shift();
  // eslint-disable-next-line no-console
  console.info('[assignment-flow]', row);
}

export function getAssignmentFlowLogBuffer(): ReadonlyArray<(typeof buffer)[number]> {
  return buffer.slice();
}

export function clearAssignmentFlowLogBuffer(): void {
  buffer.length = 0;
}
