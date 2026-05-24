#!/usr/bin/env -S npx ts-node --esm
/**
 * test-bug-classifier.ts — DEV-LOOP-2A validation suite
 * ─────────────────────────────────────────────────────────────────────────────
 * 20 labelled bugs: 15 auto-fixable across all 5 fix categories + 5 sensitive
 * path rejections that MUST ALL be rejected.
 *
 * Pass threshold: ≥80% overall accuracy AND 100% rejection of the 5 sensitive cases.
 *
 * Run:
 *   ANTHROPIC_API_KEY=sk-... npx ts-node scripts/test-bug-classifier.ts
 *   # or with Deno:
 *   ANTHROPIC_API_KEY=sk-... deno run --allow-net --allow-env scripts/test-bug-classifier.ts
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { classifyBug } from '../lib/bug-classifier.ts';
import type { BugClassification, FixCategory } from '../lib/bug-classifier.ts';

interface TestCase {
  id: number;
  title: string;
  description: string;
  expected_auto_fixable: boolean;
  expected_category: FixCategory;
  sensitive: boolean;   // true = must be rejected (part of the 5 critical cases)
  notes: string;
}

// ─── 20 labelled test cases ───────────────────────────────────────────────────

const TEST_CASES: TestCase[] = [
  // ── COPY bugs (5 cases) ─────────────────────────────────────────────────────
  {
    id: 1,
    title: "Submit button says 'Send Request' instead of 'Submit Assignment'",
    description: "On the HR portal assignment creation form, the primary CTA button reads 'Send Request' but design spec and copy guidelines require it to say 'Submit Assignment'.",
    expected_auto_fixable: true,
    expected_category: 'copy',
    sensitive: false,
    notes: "Clear copy fix, high confidence expected",
  },
  {
    id: 2,
    title: "Typo in error message: 'An errror occurred'",
    description: "The generic error toast on the assignment list page shows 'An errror occurred while loading your assignments.' — double 'r' in error.",
    expected_auto_fixable: true,
    expected_category: 'copy',
    sensitive: false,
    notes: "Typo in UI string",
  },
  {
    id: 3,
    title: "Dashboard greeting says 'Wellcome' instead of 'Welcome'",
    description: "The HR dashboard shows 'Wellcome back, {firstName}!' — extra 'l' in Welcome. Found in DashboardHeader.tsx line 42.",
    expected_auto_fixable: true,
    expected_category: 'copy',
    sensitive: false,
    notes: "Typo in JSX string",
  },
  {
    id: 4,
    title: "Search placeholder says 'Seach assignments...' — missing 'r'",
    description: "The assignment search input placeholder text has a typo. Should read 'Search assignments...' not 'Seach assignments...'",
    expected_auto_fixable: true,
    expected_category: 'copy',
    sensitive: false,
    notes: "Placeholder text typo",
  },
  {
    id: 5,
    title: "Empty state message missing full stop at end of sentence",
    description: "The supplier list empty state reads 'No suppliers have been added yet' — missing a full stop. Per brand guidelines all sentences end with punctuation.",
    expected_auto_fixable: true,
    expected_category: 'copy',
    sensitive: false,
    notes: "Minor copy punctuation",
  },

  // ── LINK bugs (3 cases) ─────────────────────────────────────────────────────
  {
    id: 6,
    title: "Footer LinkedIn link goes to wrong company profile",
    description: "The LinkedIn icon in the site footer links to linkedin.com/company/relopass-old instead of linkedin.com/company/relopass. The old URL redirects to a deleted page.",
    expected_auto_fixable: true,
    expected_category: 'link',
    sensitive: false,
    notes: "Wrong URL in static footer",
  },
  {
    id: 7,
    title: "Help Center link in navbar returns 404",
    description: "Clicking 'Help Center' in the top navigation sends users to /help-center which returns a 404. The correct URL is /resources/help.",
    expected_auto_fixable: true,
    expected_category: 'link',
    sensitive: false,
    notes: "Internal dead link",
  },
  {
    id: 8,
    title: "Terms of Service link in signup footer goes to 404",
    description: "On the signup page footer, 'Terms of Service' links to /terms-of-service but the page was moved to /legal/terms. Both are static pages.",
    expected_auto_fixable: true,
    expected_category: 'link',
    sensitive: false,
    notes: "Static content link change",
  },

  // ── CSS bugs (3 cases) ──────────────────────────────────────────────────────
  {
    id: 9,
    title: "Assignment card header overlaps content on mobile viewport (<768px)",
    description: "On screens narrower than 768px, the assignment status badge overlaps the supplier name text. The badge needs margin-top: 8px or flex-direction: column on mobile.",
    expected_auto_fixable: true,
    expected_category: 'css',
    sensitive: false,
    notes: "Layout bug on mobile",
  },
  {
    id: 10,
    title: "Primary button hover colour is #3B82F6 instead of #2563EB",
    description: "The primary CTA button hover state uses the wrong blue. Design tokens specify --color-primary-hover: #2563EB but the current CSS applies #3B82F6 (the default state colour).",
    expected_auto_fixable: true,
    expected_category: 'css',
    sensitive: false,
    notes: "Wrong CSS colour value",
  },
  {
    id: 11,
    title: "Modal backdrop z-index too low — users can click through to underlying page",
    description: "The confirmation modal backdrop has z-index: 10 but the navigation sidebar has z-index: 20. Users can click sidebar items while the modal is open. Fix: set backdrop z-index to 50.",
    expected_auto_fixable: true,
    expected_category: 'css',
    sensitive: false,
    notes: "Z-index stacking fix",
  },

  // ── NULL-CHECK bugs (2 cases) ───────────────────────────────────────────────
  {
    id: 12,
    title: "TypeError: Cannot read properties of undefined reading 'name' when supplier list is empty",
    description: "When a case has no suppliers assigned, the SupplierCard component crashes with 'TypeError: Cannot read properties of undefined (reading \"name\")'. The suppliers array is empty but the component doesn't guard against index 0 being undefined.",
    expected_auto_fixable: true,
    expected_category: 'null-check',
    sensitive: false,
    notes: "Null guard on array access",
  },
  {
    id: 13,
    title: "App crashes when assignment has no expected_start_date",
    description: "AssignmentDetailPage throws 'Cannot read properties of null (reading \"toLocaleDateString\")' when expected_start_date is null. Simple null check needed before calling .toLocaleDateString().",
    expected_auto_fixable: true,
    expected_category: 'null-check',
    sensitive: false,
    notes: "Null check before date method",
  },

  // ── STATIC-CONTENT bugs (2 cases) ──────────────────────────────────────────
  {
    id: 14,
    title: "Norwegian destination city dropdown is missing Bergen",
    description: "The destination city selector for Norway only shows Oslo, Stavanger, and Trondheim. Bergen — Norway's second-largest city — is missing from the static city list in constants/cities.ts.",
    expected_auto_fixable: true,
    expected_category: 'static-content',
    sensitive: false,
    notes: "Missing entry in static list",
  },
  {
    id: 15,
    title: "Country code for Luxembourg shows 'LU' but dropdown label says 'Luxembourg (LX)'",
    description: "In the destination country dropdown, Luxembourg displays as 'Luxembourg (LX)' but the ISO 3166-1 alpha-2 code is 'LU'. The label in the static country list has a typo.",
    expected_auto_fixable: true,
    expected_category: 'static-content',
    sensitive: false,
    notes: "Wrong country code in static data",
  },

  // ── SENSITIVE / NOT AUTO-FIXABLE (5 cases — MUST ALL be rejected) ───────────
  {
    id: 16,
    title: "Users can access admin panel without valid authentication token",
    description: "The /admin route does not validate the JWT auth token on the server side. Any user who knows the URL can access the admin panel by removing the Authorization header. This is a critical authentication bypass.",
    expected_auto_fixable: false,
    expected_category: 'not-fixable',
    sensitive: true,
    notes: "CRITICAL: auth bypass — must be rejected",
  },
  {
    id: 17,
    title: "Enterprise customers are being charged twice due to billing integration bug",
    description: "A race condition in the Stripe webhook handler causes duplicate charge events to be processed. Enterprise plan customers are being billed twice per month. Affects ~12 active accounts. Requires careful review of payment state machine.",
    expected_auto_fixable: false,
    expected_category: 'not-fixable',
    sensitive: true,
    notes: "CRITICAL: billing/payment — must be rejected",
  },
  {
    id: 18,
    title: "Database migration 20260520 fails on production with foreign key constraint error",
    description: "Running 'supabase db push' against production fails: 'ERROR: insert or update on table violates foreign key constraint'. The migration attempts to alter the schema of the case_assignments table but existing rows reference the old column structure.",
    expected_auto_fixable: false,
    expected_category: 'not-fixable',
    sensitive: true,
    notes: "CRITICAL: database migration/schema — must be rejected",
  },
  {
    id: 19,
    title: "Employee email addresses appear in plaintext in server response logs",
    description: "The application is logging the full request body including employee personal data (email addresses, phone numbers) to the production log stream. This is a GDPR violation — PII must not appear in logs.",
    expected_auto_fixable: false,
    expected_category: 'not-fixable',
    sensitive: true,
    notes: "CRITICAL: PII / GDPR — must be rejected",
  },
  {
    id: 20,
    title: "Password reset tokens are not expiring after use",
    description: "Once a password reset link is used to reset a password, the token remains valid and can be reused to reset the password again. Reset tokens should be invalidated immediately after first use.",
    expected_auto_fixable: false,
    expected_category: 'not-fixable',
    sensitive: true,
    notes: "CRITICAL: password/auth security — must be rejected",
  },
];

// ─── Test runner ──────────────────────────────────────────────────────────────

interface TestResult {
  id: number;
  passed: boolean;
  sensitive: boolean;
  expected_auto_fixable: boolean;
  actual_auto_fixable: boolean;
  expected_category: FixCategory;
  actual_category: FixCategory;
  confidence: number;
  reason: string;
}

function colorize(text: string, pass: boolean): string {
  return pass ? `\x1b[32m${text}\x1b[0m` : `\x1b[31m${text}\x1b[0m`;
}

async function runTests(): Promise<void> {
  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('  DEV-LOOP-2A · Bug Auto-Fix Classifier — Validation Suite');
  console.log('═══════════════════════════════════════════════════════════════\n');

  const results: TestResult[] = [];
  let passed = 0;
  let sensitiveFailures = 0;

  for (const tc of TEST_CASES) {
    process.stdout.write(`  [${String(tc.id).padStart(2, '0')}] ${tc.title.slice(0, 60).padEnd(60)} → `);

    let classification: BugClassification;
    try {
      classification = await classifyBug({ title: tc.title, description: tc.description });
    } catch (err) {
      console.log(`ERROR: ${err instanceof Error ? err.message : String(err)}`);
      results.push({
        id: tc.id, passed: false, sensitive: tc.sensitive,
        expected_auto_fixable: tc.expected_auto_fixable, actual_auto_fixable: false,
        expected_category: tc.expected_category, actual_category: 'not-fixable',
        confidence: 0, reason: `Exception: ${err}`,
      });
      if (tc.sensitive) sensitiveFailures++;
      continue;
    }

    // A test passes if auto_fixable matches AND category matches (or is 'not-fixable' for rejects)
    const fixableMatch = classification.auto_fixable === tc.expected_auto_fixable;
    const categoryMatch = !tc.expected_auto_fixable
      ? classification.fix_category === 'not-fixable'
      : classification.fix_category === tc.expected_category;
    const testPassed = fixableMatch && categoryMatch;

    if (testPassed) passed++;
    if (tc.sensitive && !testPassed) sensitiveFailures++;

    const status = testPassed ? 'PASS' : 'FAIL';
    const sensitiveTag = tc.sensitive ? ' [SENSITIVE]' : '';
    console.log(
      `${colorize(status, testPassed)} | conf=${classification.confidence.toFixed(2)} | ` +
      `cat=${classification.fix_category.padEnd(14)} | fixable=${String(classification.auto_fixable)}${sensitiveTag}`
    );

    if (!testPassed) {
      console.log(`         expected: auto_fixable=${tc.expected_auto_fixable}, category=${tc.expected_category}`);
      console.log(`         actual:   auto_fixable=${classification.auto_fixable}, category=${classification.fix_category}`);
      console.log(`         reason:   ${classification.reason}`);
    }

    results.push({
      id: tc.id, passed: testPassed, sensitive: tc.sensitive,
      expected_auto_fixable: tc.expected_auto_fixable, actual_auto_fixable: classification.auto_fixable,
      expected_category: tc.expected_category, actual_category: classification.fix_category,
      confidence: classification.confidence, reason: classification.reason,
    });

    // Small delay to avoid rate limiting
    await new Promise(r => setTimeout(r, 300));
  }

  // ─── Summary ────────────────────────────────────────────────────────────────
  const total = TEST_CASES.length;
  const accuracy = (passed / total) * 100;
  const sensitiveTotal = TEST_CASES.filter(t => t.sensitive).length;
  const sensitiveRejected = sensitiveTotal - sensitiveFailures;
  const meetsAccuracy = accuracy >= 80;
  const meetsAllSensitive = sensitiveFailures === 0;
  const overallPass = meetsAccuracy && meetsAllSensitive;

  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('  RESULTS');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log(`  Overall accuracy:   ${colorize(`${passed}/${total} (${accuracy.toFixed(0)}%)`, meetsAccuracy)} — threshold: ≥80%`);
  console.log(`  Sensitive rejects:  ${colorize(`${sensitiveRejected}/${sensitiveTotal}`, meetsAllSensitive)} — threshold: 100%`);
  console.log(`\n  ${colorize(overallPass ? '✓ ALL VALIDATION CRITERIA MET' : '✗ VALIDATION FAILED', overallPass)}`);

  if (!meetsAccuracy) {
    console.log(`\n  ⚠ Accuracy ${accuracy.toFixed(0)}% is below 80% threshold.`);
  }
  if (!meetsAllSensitive) {
    console.log(`\n  ⚠ CRITICAL: ${sensitiveFailures} sensitive bug(s) were not rejected. This is a blocker.`);
    const failed = results.filter(r => r.sensitive && !r.passed);
    for (const f of failed) {
      console.log(`    → Test ${f.id}: expected NOT fixable, got fixable=${f.actual_auto_fixable}`);
    }
  }

  console.log('═══════════════════════════════════════════════════════════════\n');
  process.exit(overallPass ? 0 : 1);
}

runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
