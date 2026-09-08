#!/usr/bin/env -S npx ts-node --esm
/**
 * test-autofix-blocklist.ts — DEV-LOOP-2B validation suite
 * ─────────────────────────────────────────────────────────────────────────────
 * Validates isBlockedPath(), checkBugSafety(), and isAutoFixSafe().
 *
 * Categories tested:
 *   Path checks:    auth, billing, migrations, webhook, stripe, session,
 *                   secret, token, password, schema, PII paths
 *   Keyword checks: auth, token, password, session, billing, payment,
 *                   charge, Stripe, migration, schema change, PII, email address
 *   Safe cases:     copy, link, css, null-check, static-content
 *   Combined gate:  isAutoFixSafe()
 *
 * Pass threshold: 100% (zero false-negatives allowed)
 *
 * Run:
 *   npx ts-node scripts/test-autofix-blocklist.ts
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { isBlockedPath, checkBugSafety, isAutoFixSafe } from '../lib/autofix-blocklist.ts';

// ─── Colour helpers ───────────────────────────────────────────────────────────

function green(s: string) { return `\x1b[32m${s}\x1b[0m`; }
function red(s: string)   { return `\x1b[31m${s}\x1b[0m`; }
function bold(s: string)  { return `\x1b[1m${s}\x1b[0m`; }

// ─── Test types ───────────────────────────────────────────────────────────────

interface PathTestCase {
  kind: 'path';
  id: number;
  filePath: string;
  expectedBlocked: boolean;
  notes: string;
}

interface KeywordTestCase {
  kind: 'keyword';
  id: number;
  description: string;
  expectedSafe: boolean;
  notes: string;
}

interface CombinedTestCase {
  kind: 'combined';
  id: number;
  filePath: string;
  description: string;
  expectedSafe: boolean;
  notes: string;
}

type TestCase = PathTestCase | KeywordTestCase | CombinedTestCase;

// ─── Test cases ───────────────────────────────────────────────────────────────

const TEST_CASES: TestCase[] = [

  // ── PATH CHECKS: must be BLOCKED ─────────────────────────────────────────────

  {
    kind: 'path', id: 1,
    filePath: 'src/auth/login.ts',
    expectedBlocked: true,
    notes: 'Auth directory — critical',
  },
  {
    kind: 'path', id: 2,
    filePath: 'frontend/src/lib/session.ts',
    expectedBlocked: true,
    notes: 'Session file in lib directory',
  },
  {
    kind: 'path', id: 3,
    filePath: 'supabase/migrations/20260523_alter_users.sql',
    expectedBlocked: true,
    notes: 'Supabase migrations directory',
  },
  {
    kind: 'path', id: 4,
    filePath: 'supabase/functions/stripe-webhook/index.ts',
    expectedBlocked: true,
    notes: 'Stripe webhook Edge Function',
  },
  {
    kind: 'path', id: 5,
    filePath: 'backend/app/routers/billing.py',
    expectedBlocked: true,
    notes: 'Billing router',
  },
  {
    kind: 'path', id: 6,
    filePath: 'lib/tokenUtils.ts',
    expectedBlocked: true,
    notes: 'Token utility file',
  },
  {
    kind: 'path', id: 7,
    filePath: 'src/utils/passwordHasher.ts',
    expectedBlocked: true,
    notes: 'Password hashing utility',
  },
  {
    kind: 'path', id: 8,
    filePath: 'backend/migrations/0042_update_schema.py',
    expectedBlocked: true,
    notes: 'Django-style migrations directory',
  },
  {
    kind: 'path', id: 9,
    filePath: 'config/secrets.ts',
    expectedBlocked: true,
    notes: 'Secrets config file',
  },
  {
    kind: 'path', id: 10,
    filePath: '.env.production',
    expectedBlocked: true,
    notes: 'Production env file',
  },
  {
    kind: 'path', id: 11,
    filePath: 'src/lib/encryption.ts',
    expectedBlocked: true,
    notes: 'Encryption module',
  },
  {
    kind: 'path', id: 12,
    filePath: '.github/workflows/deploy.yml',
    expectedBlocked: true,
    notes: 'GitHub Actions workflow',
  },

  // ── PATH CHECKS: must be ALLOWED ─────────────────────────────────────────────

  {
    kind: 'path', id: 13,
    filePath: 'frontend/src/components/SupplierCard.tsx',
    expectedBlocked: false,
    notes: 'Normal UI component — safe',
  },
  {
    kind: 'path', id: 14,
    filePath: 'frontend/src/styles/globals.css',
    expectedBlocked: false,
    notes: 'CSS stylesheet — safe',
  },
  {
    kind: 'path', id: 15,
    filePath: 'frontend/src/constants/cities.ts',
    expectedBlocked: false,
    notes: 'Static content file — safe',
  },
  {
    kind: 'path', id: 16,
    filePath: 'frontend/src/components/DashboardHeader.tsx',
    expectedBlocked: false,
    notes: 'Dashboard header component — safe',
  },
  {
    kind: 'path', id: 17,
    filePath: 'lib/bug-classifier.ts',
    expectedBlocked: false,
    notes: 'Bug classifier lib — safe',
  },

  // ── KEYWORD CHECKS: must be REJECTED (safe=false) ────────────────────────────

  {
    kind: 'keyword', id: 18,
    description: 'Users can access admin panel without valid authentication token — critical auth bypass.',
    expectedSafe: false,
    notes: 'Authentication keyword',
  },
  {
    kind: 'keyword', id: 19,
    description: 'Enterprise customers are being charged twice due to billing integration bug.',
    expectedSafe: false,
    notes: 'Billing / charge keyword',
  },
  {
    kind: 'keyword', id: 20,
    description: 'Database migration 20260520 fails with foreign key constraint error on production.',
    expectedSafe: false,
    notes: 'Migration keyword',
  },
  {
    kind: 'keyword', id: 21,
    description: 'Employee email addresses and phone numbers appear in plaintext in server response logs — GDPR violation.',
    expectedSafe: false,
    notes: 'PII / GDPR / email address keywords',
  },
  {
    kind: 'keyword', id: 22,
    description: 'Password reset tokens are not expiring after first use — security risk.',
    expectedSafe: false,
    notes: 'Password + token keywords',
  },
  {
    kind: 'keyword', id: 23,
    description: 'Session cookie is not invalidated after logout.',
    expectedSafe: false,
    notes: 'Session + cookie keywords',
  },
  {
    kind: 'keyword', id: 24,
    description: 'Stripe webhook is processing duplicate payment events, causing double charges.',
    expectedSafe: false,
    notes: 'Stripe + payment + charge keywords',
  },
  {
    kind: 'keyword', id: 25,
    description: 'Schema change required to add nullable column to case_assignments table.',
    expectedSafe: false,
    notes: 'Schema change keyword',
  },
  {
    kind: 'keyword', id: 26,
    description: 'JWT token validation skipped for certain admin routes.',
    expectedSafe: false,
    notes: 'JWT + token keywords',
  },
  {
    kind: 'keyword', id: 27,
    description: 'Subscription downgrade does not cancel upcoming invoice on Stripe.',
    expectedSafe: false,
    notes: 'Subscription + invoice + Stripe keywords',
  },
  {
    kind: 'keyword', id: 28,
    description: 'Race condition in Stripe webhook handler causes duplicate subscription activations.',
    expectedSafe: false,
    notes: 'Race condition (billing context) keyword',
  },
  {
    kind: 'keyword', id: 29,
    description: 'CSRF protection missing on the password change endpoint.',
    expectedSafe: false,
    notes: 'CSRF + password keywords',
  },

  // ── KEYWORD CHECKS: must be SAFE (safe=true) ─────────────────────────────────

  {
    kind: 'keyword', id: 30,
    description: "Submit button says 'Send Request' instead of 'Submit Assignment'. Simple copy fix.",
    expectedSafe: true,
    notes: 'Copy bug — safe',
  },
  {
    kind: 'keyword', id: 31,
    description: "Help Center link in navbar returns 404. Should point to /resources/help.",
    expectedSafe: true,
    notes: 'Link bug — safe',
  },
  {
    kind: 'keyword', id: 32,
    description: "Assignment card header overlaps content on mobile (<768px). Needs margin-top: 8px.",
    expectedSafe: true,
    notes: 'CSS layout bug — safe',
  },
  {
    kind: 'keyword', id: 33,
    description: "TypeError: Cannot read properties of undefined reading 'name' when suppliers array is empty.",
    expectedSafe: true,
    notes: 'Null-check bug — safe',
  },
  {
    kind: 'keyword', id: 34,
    description: "Norwegian destination city dropdown missing Bergen from the static city list.",
    expectedSafe: true,
    notes: 'Static content bug — safe',
  },

  // ── COMBINED GATE TESTS ───────────────────────────────────────────────────────

  {
    kind: 'combined', id: 35,
    filePath: 'frontend/src/components/SupplierCard.tsx',
    description: "Supplier name overflows card on narrow viewport. Needs text-overflow: ellipsis.",
    expectedSafe: true,
    notes: 'Safe file + safe description → should pass',
  },
  {
    kind: 'combined', id: 36,
    filePath: 'src/auth/middleware.ts',
    description: "Typo in error message: 'Unauthorised' instead of 'Unauthorized'.",
    expectedSafe: false,
    notes: 'Blocked path (even if description seems safe) → should reject',
  },
  {
    kind: 'combined', id: 37,
    filePath: 'frontend/src/components/Button.tsx',
    description: "Payment flow is broken — users are being charged twice via Stripe webhook.",
    expectedSafe: false,
    notes: 'Safe path but dangerous description → should reject',
  },
  {
    kind: 'combined', id: 38,
    filePath: 'supabase/migrations/20260525_add_column.sql',
    description: "Add nullable column to assignments table — migration failing due to FK constraint.",
    expectedSafe: false,
    notes: 'Both path and description are dangerous',
  },
];

// ─── Test runner ──────────────────────────────────────────────────────────────

function runTests(): void {
  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('  DEV-LOOP-2B · Autofix Blocklist — Validation Suite');
  console.log('═══════════════════════════════════════════════════════════════\n');

  let passed = 0;
  let failed = 0;
  const failures: string[] = [];

  for (const tc of TEST_CASES) {
    let testPassed: boolean;
    let detail: string;

    if (tc.kind === 'path') {
      const blocked = isBlockedPath(tc.filePath);
      testPassed = blocked === tc.expectedBlocked;
      const expected = tc.expectedBlocked ? 'BLOCKED' : 'ALLOWED';
      const actual   = blocked             ? 'BLOCKED' : 'ALLOWED';
      detail = `path="${tc.filePath.slice(0, 55)}" expected=${expected} actual=${actual}`;
    } else if (tc.kind === 'keyword') {
      const result = checkBugSafety(tc.description);
      testPassed = result.safe === tc.expectedSafe;
      detail = `safe=${result.safe} expected=${tc.expectedSafe}${!result.safe ? ` matched="${result.matched_keyword}"` : ''}`;
    } else {
      const result = isAutoFixSafe(tc.filePath, tc.description);
      testPassed = result.safe === tc.expectedSafe;
      detail = `safe=${result.safe} expected=${tc.expectedSafe} | ${result.reason.slice(0, 60)}`;
    }

    const status = testPassed ? green('PASS') : red('FAIL');
    const label = `[${String(tc.id).padStart(2, '0')}] ${tc.notes.slice(0, 50).padEnd(50)}`;
    console.log(`  ${label} → ${status} | ${detail}`);

    if (testPassed) {
      passed++;
    } else {
      failed++;
      failures.push(`  Test ${tc.id}: ${tc.notes}`);
    }
  }

  const total = TEST_CASES.length;
  const allPassed = failed === 0;

  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log('  RESULTS');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log(`  ${allPassed ? green('✓') : red('✗')} ${passed}/${total} tests passed`);

  if (!allPassed) {
    console.log(`\n  ${red('FAILURES:')}`);
    for (const f of failures) console.log(red(f));
  }

  console.log(`\n  ${allPassed ? green('✓ ALL VALIDATION CRITERIA MET') : red('✗ VALIDATION FAILED — DO NOT DEPLOY')}`);
  console.log('═══════════════════════════════════════════════════════════════\n');

  process.exit(allPassed ? 0 : 1);
}

runTests();
