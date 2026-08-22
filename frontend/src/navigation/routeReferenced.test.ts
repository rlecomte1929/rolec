/**
 * Every ROUTE_DEFS entry must have at least one inbound navigation reference.
 *
 * THE BUG CLASS. `routeDefsMounted.test.ts` (sibling) proves a declared route is
 * mounted in App.tsx. Mounted is not the same as reachable: a route can be declared,
 * mounted, rendered correctly, and linked from nowhere — so the only way to open it is
 * to type the URL. Nobody types URLs, so the page is dead, and work keeps shipping into
 * it. `/hr/employees` was in exactly that state: its only inbound links were the command
 * centre's `noCasesYet` empty-state CTA and the back-link on its own detail page, so the
 * team roster became unreachable the moment a company had one case.
 *
 * WHAT COUNTS AS A REFERENCE. Any of these, in any src file other than the declaration
 * (navigation/routes.ts) and the mounting (App.tsx):
 *   buildRoute('routeKey')        ← the dominant idiom in this codebase
 *   ROUTE_DEFS.routeKey           ← direct, e.g. in roleHome.ts and the sidebar
 *   '/literal/path'               ← string literal matching the route's declared path
 *
 * WHAT THIS GUARD DOES NOT PROVE — read before trusting it. This is a NECESSARY, not a
 * sufficient, condition for reachability. It proves *something* points at the route. It
 * does NOT prove a user can get there: a route referenced only by another orphaned page
 * is still unreachable, and this test will pass it. Proving true reachability needs a
 * link graph walked from the sidebar and role homes, which needs a path→component map
 * out of App.tsx's lazy imports. That is worth building; it is not what this is.
 *
 * Consequently a BASELINE is unavoidable here, unlike scripts/check_no_vendored_deps.py
 * where every violator could be removed in the same commit. Each entry below is a route
 * nothing currently links to. Draining the list means, per route, either wiring a link
 * from a reachable surface or deleting the route and its page — both product decisions,
 * not mechanical ones. The guard's job meanwhile is that no NEW orphan is added silently.
 *
 * Baseline captured 2026-08-22 (AIQ-2086): 54 entries; 53 after AIQ-2087 removed
 * `hrPolicyReality` (the Policy-vs-Reality page) outright rather than wiring it up.
 */
import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';
import { describe, it, expect } from 'vitest';

const SRC = join(__dirname, '..');

/** ROUTE_DEFS key → declared path. */
function routeDefs(): Map<string, string> {
  const src = readFileSync(join(SRC, 'navigation/routes.ts'), 'utf8');
  return new Map(
    [...src.matchAll(/^ {2}(\w+):\s*\{\s*path:\s*'([^']+)'/gm)].map((m) => [m[1]!, m[2]!]),
  );
}

/** Every .ts/.tsx under src/, excluding tests, the declaration and the mounting. */
function sourceFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist') continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      sourceFiles(full, acc);
    } else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) {
      acc.push(full);
    }
  }
  return acc;
}

/** Route keys with >= 1 inbound reference. */
function referencedKeys(): Set<string> {
  const defs = routeDefs();
  const excluded = new Set([join(SRC, 'navigation/routes.ts'), join(SRC, 'App.tsx')]);
  const referenced = new Set<string>();

  for (const file of sourceFiles(SRC)) {
    if (excluded.has(file)) continue;
    const text = readFileSync(file, 'utf8');
    for (const [key, path] of defs) {
      if (referenced.has(key)) continue;
      if (
        new RegExp(`buildRoute\\(\\s*['"\`]${key}['"\`]`).test(text) ||
        new RegExp(`\\bROUTE_DEFS\\.${key}\\b`).test(text) ||
        text.includes(`'${path}'`) ||
        text.includes(`"${path}"`) ||
        text.includes(`\`${path}\``)
      ) {
        referenced.add(key);
      }
    }
  }
  return referenced;
}

/**
 * Routes nothing links to, as of 2026-08-22. Drain this list; do not grow it.
 * A new entry here means a page was built that no user can open.
 */
const KNOWN_UNREFERENCED = [
  'adminAbTests', 'adminAiQuestions', 'adminAttestations', 'adminAutopilotMetrics',
  'adminCandidateBeam', 'adminCorrectionsTrends', 'adminCrawlSchedules', 'adminErrors',
  'adminFreshnessCities', 'adminFreshnessSources', 'adminLeads', 'adminMarketingAnalytics',
  'adminMessages', 'adminMissionControl', 'adminMobilityCaseInspect', 'adminOpsDestinations',
  'adminOpsErrors', 'adminOpsNotifications', 'adminOpsReviewers', 'adminPrompts',
  'adminRelocations', 'adminResearch', 'adminReviewQueueWorkload', 'adminSourceChangeReviews',
  'adminSourceMonitor', 'adminSpecialistReview', 'adminSupport', 'adminWorkflowFunnel',
  'auditNavigation', 'caseServices', 'caseServicesConclusion', 'caseServicesEstimate',
  'caseServicesRecommendations', 'compliance', 'employeeCaseDossierBuild', 'employeeDocuments',
  'employeePolicy', 'employeeRichProfile', 'hrAnalytics', 'hrCaseDossier',
  'hrEmployeeDashboard', 'hrErasureRequests', 'hrPackage', 'hrPolicyBuilder',
  'hrPolicyDashboard', 'hrPolicyManagement', 'hrVendorCuration',
  'notificationSettings', 'providerPortal', 'quoteRfqDetail', 'servicesConclusion',
  'supplierQuote', 'vendorRfq',
];

describe('every declared route has an inbound reference', () => {
  it('has no unreferenced ROUTE_DEFS entry beyond the known list', () => {
    const referenced = referencedKeys();
    const unreferenced = [...routeDefs().keys()].filter((k) => !referenced.has(k)).sort();

    expect(
      unreferenced,
      'A ROUTE_DEFS entry that nothing links to can only be opened by typing its URL, so ' +
        'in practice it is dead — and work keeps shipping into dead pages. Link it from a ' +
        'surface a user can already reach, or delete the route and its page. If you just ' +
        'wired one up, remove it from KNOWN_UNREFERENCED.',
    ).toEqual([...KNOWN_UNREFERENCED].sort());
  });

  it('sanity: the resolver finds real references (no blanket false-negative)', () => {
    // Without this, a broken resolver would return an empty set and the test above would
    // "pass" only because everything looked unreferenced — or, if it matched everything,
    // pass vacuously the other way. Pin both ends.
    const referenced = referencedKeys();
    expect(referenced.has('hrDashboard')).toBe(true); // buildRoute('hrDashboard'), sidebar + command centre
    expect(referenced.has('hrEmployees')).toBe(true); // buildRoute('hrEmployees'), sidebar
    expect(referenced.has('employeeJourney')).toBe(true); // buildRoute + literal path
    expect(referenced.has('adminSupport')).toBe(false); // genuinely orphaned, in the baseline
    expect(referenced.size).toBeGreaterThan(100);
  });
});
