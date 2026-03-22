/**
 * Lightweight client-side markers for the employee case / wizard journey.
 * Enable with VITE_EMPLOYEE_PERF_LOG=1 or use DEV (console only).
 *
 * Entry / bootstrap (assignment resolution, claim skip): also enable with
 * VITE_EMPLOYEE_ENTRY_LOG=1 in production builds when you need timings without full dev noise.
 */

const perfEnabled = () =>
  import.meta.env.DEV || import.meta.env.VITE_EMPLOYEE_PERF_LOG === 'true' || import.meta.env.VITE_EMPLOYEE_PERF_LOG === '1';

const entryEnabled = () =>
  perfEnabled() ||
  import.meta.env.VITE_EMPLOYEE_ENTRY_LOG === 'true' ||
  import.meta.env.VITE_EMPLOYEE_ENTRY_LOG === '1';

export function logEmployeeJourney(event: string, detail?: Record<string, unknown>): void {
  if (!perfEnabled()) return;
  const payload = { t: performance.now(), event, ...detail };
  // eslint-disable-next-line no-console
  console.info('[employee-journey]', payload);
}

/** Assignment resolution on /employee/dashboard (optional prod logging). */
export function logEmployeeEntry(event: string, detail?: Record<string, unknown>): void {
  if (!entryEnabled()) return;
  const payload = { t: performance.now(), event, ...detail };
  // eslint-disable-next-line no-console
  console.info('[employee-entry]', payload);
}
