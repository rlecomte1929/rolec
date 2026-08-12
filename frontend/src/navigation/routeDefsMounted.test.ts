/**
 * Every ROUTE_DEFS entry must actually be mounted in App.tsx.
 *
 * The bug this exists for: `hrCaseDossier` ('/hr/cases/:caseId/dossier') was declared in
 * routes.ts in 2635d030 and never added to App.tsx. `HrCaseDossierPage.tsx` was imported by
 * nothing. Every hit on that URL fell through to <Route path="*"> → NotFoundRedirect →
 * /hr/dashboard, so the page looked like it "redirected" rather than like it was missing.
 * It stayed dead for months, and a later change (the destination-requirements section built
 * for HR) shipped into it — reviewed, merged, deployed, and unreachable.
 *
 * navigateTargets.test.ts is the sibling guard and could not catch this: it checks that
 * navigate() targets resolve against the route table, and it treats a ROUTE_DEFS entry as
 * proof the route exists. That is exactly the assumption that fails here — declaring a path
 * is not mounting it. This test closes the other half.
 *
 * A route can be mounted three ways, and all three count:
 *   <Route path="/literal">
 *   <Route path={ROUTE_DEFS.key.path}>
 *   <Route path={WIZARD_ROUTES.KEY}>      (src/routes.ts — same path, different symbol;
 *                                          employeeCasePlan is mounted only this way)
 * Comparing symbol names instead of resolved path strings produces false positives.
 */
import { readFileSync } from 'fs';
import { join } from 'path';
import { describe, it, expect } from 'vitest';

const SRC = join(__dirname, '..');

/** ROUTE_DEFS key → path. */
function routeDefPaths(): Map<string, string> {
  const src = readFileSync(join(SRC, 'navigation/routes.ts'), 'utf8');
  return new Map([...src.matchAll(/^ {2}(\w+):\s*\{\s*path:\s*'([^']+)'/gm)].map((m) => [m[1]!, m[2]!]));
}

/** WIZARD_ROUTES (src/routes.ts) key → path. */
function wizardRoutePaths(): Map<string, string> {
  const src = readFileSync(join(SRC, 'routes.ts'), 'utf8');
  return new Map([...src.matchAll(/^ {2}(\w+):\s*"([^"]+)"/gm)].map((m) => [m[1]!, m[2]!]));
}

/** Every path App.tsx actually mounts, resolved through all three forms. */
function mountedPaths(): Set<string> {
  const app = readFileSync(join(SRC, 'App.tsx'), 'utf8');
  const defs = routeDefPaths();
  const wizard = wizardRoutePaths();
  const mounted = new Set<string>();

  for (const m of app.matchAll(/<Route\s+path="([^"]+)"/g)) mounted.add(m[1]!);
  for (const m of app.matchAll(/<Route\s+path=\{ROUTE_DEFS\.(\w+)\.path\}/g)) {
    const p = defs.get(m[1]!);
    if (p) mounted.add(p);
  }
  for (const m of app.matchAll(/<Route\s+path=\{WIZARD_ROUTES\.(\w+)\}/g)) {
    const p = wizard.get(m[1]!);
    if (p) mounted.add(p);
  }
  return mounted;
}

/**
 * Pre-existing unmounted declarations, enumerated so no NEW one can be added silently.
 *
 * `hrPolicyBuilderReview` is a LIVE dead link, not merely an unused declaration:
 * HrPolicy.tsx's "review & publish" CTA calls navigate(buildRoute('hrPolicyBuilderReview')),
 * which bounces HR to the dashboard. It needs a page decision, so it is reported rather than
 * papered over here. The other two are referenced by nothing.
 */
const KNOWN_UNMOUNTED = [
  'employeeCaseDossierBuild',
  'hrPolicyBuilderDocuments',
  'hrPolicyBuilderReview',
];

describe('every declared route is mounted', () => {
  it('has no unmounted ROUTE_DEFS entry beyond the known list', () => {
    const mounted = mountedPaths();
    const unmounted = [...routeDefPaths()]
      .filter(([, path]) => !mounted.has(path))
      .map(([key]) => key)
      .sort();

    expect(
      unmounted,
      'A ROUTE_DEFS entry with no <Route> in App.tsx is dead: the catch-all swallows it and ' +
        'redirects to the role home, so it fails silently. Mount it in App.tsx. If you just ' +
        'fixed one of the known offenders, delete it from KNOWN_UNMOUNTED.',
    ).toEqual([...KNOWN_UNMOUNTED].sort());
  });

  it('sanity: the guard resolves real mountings (no blanket false-negative)', () => {
    // If the resolver silently matched nothing, the first test would pass vacuously.
    const mounted = mountedPaths();
    expect(mounted.has('/hr/cases/:caseId/dossier')).toBe(true); // ROUTE_DEFS form
    expect(mounted.has('/employee/case/:caseId/plan')).toBe(true); // WIZARD_ROUTES form
    expect(mounted.size).toBeGreaterThan(150);
  });
});
