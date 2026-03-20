/**
 * Lightweight client-side markers for the employee case / wizard journey.
 * Enable with VITE_EMPLOYEE_PERF_LOG=1 or use DEV (console only).
 */

const enabled = () =>
  import.meta.env.DEV || import.meta.env.VITE_EMPLOYEE_PERF_LOG === 'true' || import.meta.env.VITE_EMPLOYEE_PERF_LOG === '1';

export function logEmployeeJourney(event: string, detail?: Record<string, unknown>): void {
  if (!enabled()) return;
  const payload = { t: performance.now(), event, ...detail };
  // eslint-disable-next-line no-console
  console.info('[employee-journey]', payload);
}
