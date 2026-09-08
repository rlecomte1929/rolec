/**
 * Resolve mobility_cases.id for the employee case summary (product order).
 * Backend field is authoritative; query param is debug-only; demo env is dev-only.
 */
export function resolveMobilityCaseIdForSummary(opts: {
  backendMobilityCaseId: string | null | undefined;
  debugQueryMcid: string | null | undefined;
  devDemoEnvMobilityCaseId: string | null | undefined;
  isDev: boolean;
}): string | null {
  const fromApi = opts.backendMobilityCaseId?.trim();
  if (fromApi) return fromApi;
  const q = opts.debugQueryMcid?.trim();
  if (q) return q;
  if (opts.isDev) {
    const d = opts.devDemoEnvMobilityCaseId?.trim();
    if (d) return d;
  }
  return null;
}
