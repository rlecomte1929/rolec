/**
 * autofix-blocklist.ts — DEV-LOOP-2B
 * ─────────────────────────────────────────────────────────────────────────────
 * Hard blocklist layer that MUST run before any automated code fix is attempted.
 *
 * Two independent checks:
 *   1. isBlockedPath(filePath)    — rejects files in protected directories
 *   2. checkBugSafety(description) — rejects bug descriptions with sensitive keywords
 *
 * Both checks are case-insensitive and have zero external dependencies.
 * A false-negative (allowing something dangerous through) is ALWAYS worse than
 * a false-positive (blocking a safe fix).
 *
 * Usage:
 *   import { isBlockedPath, checkBugSafety } from '../lib/autofix-blocklist';
 *
 *   if (isBlockedPath(filePath)) throw new Error('File is in a protected directory');
 *   const safety = checkBugSafety(bugDescription);
 *   if (!safety.safe) throw new Error(safety.reason);
 * ─────────────────────────────────────────────────────────────────────────────
 */

// ─── Protected path patterns ──────────────────────────────────────────────────
// Glob-style patterns. Each pattern is converted to a regex at module load time.
// Rules:
//   **  → matches any path segment(s) including slashes
//   *   → matches any characters except slash
//   ?   → matches exactly one character (except slash)
//
// Add new patterns here whenever a new sensitive area is introduced.

export const BLOCKED_PATHS: readonly string[] = [
  // Auth & identity
  'auth/**',
  '**/auth/**',
  '**/auth/*',
  '**/authenticate*',
  '**/authentication*',
  '**/authoriz*',

  // Tokens & sessions
  '**/token*',
  '**/session*',
  '**/cookie*',
  '**/jwt*',
  '**/oauth*',

  // Credentials & secrets
  '**/secret*',
  '**/credential*',
  '**/password*',
  '**/passwd*',
  '**/api-key*',
  '**/apikey*',
  '**/.env*',
  '**/env.local*',

  // Billing & payments
  'billing/**',
  '**/billing/**',
  '**/billing/*',
  '**/billing*',       // also files named billing.py, billing.ts, etc.
  '**/payment*',
  '**/invoice*',
  '**/subscription*',
  '**/stripe*',        // files named stripe* (stripe.ts, stripeClient.ts)
  '**/stripe*/**',     // directories starting with stripe (stripe-webhook/)
  '**/charge*',
  '**/pricing*',
  '**/webhook*',       // files named webhook*
  '**/webhook*/**',    // directories starting with webhook

  // Database migrations & schema
  'migrations/**',
  '**/migrations/**',
  '**/migrations/*',
  'supabase/migrations/**',
  '**/migration*',
  '**/schema*',

  // PII & GDPR
  '**/pii*',
  '**/gdpr*',
  '**/personal-data*',
  '**/data-export*',
  '**/user-data*',

  // Security & permissions
  '**/permission*',
  '**/rbac*',
  '**/role*',
  '**/acl*',
  '**/access-control*',
  '**/policy*',

  // Encryption & certificates
  '**/encrypt*',
  '**/decrypt*',
  '**/hash*',
  '**/certificate*',
  '**/ssl*',
  '**/tls*',
  '**/crypto*',

  // Infrastructure & deployment
  '**/deploy*',
  '**/infra*',
  '**/terraform*',
  '**/kubernetes*',
  '**/docker*',
  '**/.ci/**',          // hidden CI directories
  '**/ci/**',           // directories named ci/ (not files with 'ci' in name)
  '**/.github/**',
  '**/cron*',
  '**/seed*',
] as const;

// ─── Glob → RegExp conversion ─────────────────────────────────────────────────

/**
 * Convert a glob pattern to a case-insensitive RegExp.
 * Supports **, *, ? wildcards.
 * The pattern is anchored so it must match the full path (after normalisation).
 */
function globToRegex(pattern: string): RegExp {
  let regexStr = '';
  let i = 0;
  while (i < pattern.length) {
    if (pattern[i] === '*' && pattern[i + 1] === '*') {
      // ** → match everything including slashes, then optional trailing slash
      regexStr += '.*';
      i += 2;
      // Skip optional following slash
      if (pattern[i] === '/') i++;
    } else if (pattern[i] === '*') {
      // * → match everything except slash
      regexStr += '[^/]*';
      i++;
    } else if (pattern[i] === '?') {
      // ? → match single char except slash
      regexStr += '[^/]';
      i++;
    } else {
      // Escape regex metacharacters
      regexStr += pattern[i].replace(/[.+^${}()|[\]\\]/g, '\\$&');
      i++;
    }
  }
  return new RegExp(`^${regexStr}$`, 'i');
}

// Pre-compile all patterns at module load time (zero runtime cost per call)
const COMPILED_PATTERNS: readonly RegExp[] = BLOCKED_PATHS.map(globToRegex);

// ─── isBlockedPath ────────────────────────────────────────────────────────────

/**
 * Returns true if the given file path matches any blocked pattern.
 *
 * Normalises the path by:
 *   - Removing leading './' or '/'
 *   - Converting backslashes to forward slashes (Windows compat)
 *
 * @param filePath  Relative or absolute file path
 */
export function isBlockedPath(filePath: string): boolean {
  // Normalise
  const normalised = filePath
    .replace(/\\/g, '/')          // backslash → forward slash
    .replace(/^\.\//, '')         // strip leading ./
    .replace(/^\//, '');          // strip leading /

  for (const pattern of COMPILED_PATTERNS) {
    if (pattern.test(normalised)) {
      return true;
    }
  }
  return false;
}

/**
 * Returns the matching pattern name if the path is blocked, or null if safe.
 * Useful for generating human-readable rejection reasons.
 */
export function blockedPathReason(filePath: string): string | null {
  const normalised = filePath
    .replace(/\\/g, '/')
    .replace(/^\.\//, '')
    .replace(/^\//, '');

  for (let i = 0; i < COMPILED_PATTERNS.length; i++) {
    if (COMPILED_PATTERNS[i].test(normalised)) {
      return BLOCKED_PATHS[i];
    }
  }
  return null;
}

// ─── Sensitive keyword blocklist for bug descriptions ─────────────────────────
// These are checked against the bug title + description (case-insensitive).
// Ordered from most specific to most general to aid in clear rejection messages.

export interface SafetyCheckResult {
  safe: boolean;
  reason: string;
  matched_keyword?: string;
}

const SAFETY_KEYWORDS: readonly string[] = [
  // Auth & identity
  'authentication bypass',
  'auth bypass',
  'authentication',
  'authoriz',      // authorization, authorize
  'jwt',
  'json web token',
  'session token',
  'session cookie',
  'session',
  'login',
  'logout',
  'sign-in',
  'sign in',
  'sign out',
  'sign-out',
  'sso',
  'oauth',
  'saml',
  'mfa',
  '2fa',
  'two-factor',
  'single sign',

  // Credentials
  'password',
  'passwd',
  'credential',
  'api key',
  'apikey',
  'api_key',
  'secret key',
  'access key',
  'private key',
  'token',           // generic — catches auth tokens, reset tokens, etc.

  // Billing & payments
  'billing',
  'charge',
  'charged',
  'double charge',
  'overcharged',
  'payment',
  'invoice',
  'subscription',
  'stripe',
  'webhook',
  'price',
  'pricing',
  'plan upgrade',
  'plan downgrade',
  'refund',

  // Database migrations & schema
  'migration',
  'schema change',
  'schema migration',
  'alter table',
  'drop table',
  'drop column',
  'add column',
  'foreign key',
  'constraint',
  'supabase db push',
  'db push',

  // PII & GDPR
  'pii',
  'gdpr',
  'personal data',
  'personally identifiable',
  'email address',
  'phone number',
  'passport',
  'national id',
  'date of birth',
  'home address',
  'bank account',
  'credit card',
  'social security',

  // Security vulnerabilities
  'sql injection',
  'xss',
  'cross-site scripting',
  'csrf',
  'cross-site request',
  'security vulnerability',
  'vulnerability',
  'exploit',
  'privilege escalation',
  'admin bypass',
  'access control',
  'rbac',
  'permission',
  'unauthorized access',
  'unauthenticated',

  // Encryption & certificates
  'encryption',
  'decryption',
  'certificate',
  'ssl',
  'tls',
  'https',
  'hash collision',

  // Sensitive infrastructure
  'production database',
  'prod db',
  'production migration',
  'data loss',
  'race condition',       // billing/payment race conditions especially
  'deadlock',
  'data integrity',
] as const;

/**
 * Scan a bug title + description for sensitive keywords.
 * Returns { safe: true } if no sensitive content is found.
 * Returns { safe: false, reason, matched_keyword } on any match.
 *
 * Case-insensitive. Matches partial words to catch variations
 * (e.g. 'authoriz' matches 'authorization', 'authorize', 'authorized').
 *
 * @param bugDescription  Bug title and/or description text
 */
export function checkBugSafety(bugDescription: string): SafetyCheckResult {
  const lower = bugDescription.toLowerCase();

  for (const keyword of SAFETY_KEYWORDS) {
    if (lower.includes(keyword.toLowerCase())) {
      return {
        safe: false,
        reason: `Bug description contains sensitive keyword "${keyword}" — manual review required. Auto-fix is not permitted for bugs involving auth, billing, migrations, PII, or security.`,
        matched_keyword: keyword,
      };
    }
  }

  return {
    safe: true,
    reason: 'No sensitive keywords detected — safe to proceed with auto-fix classifier.',
  };
}

// ─── Combined safety gate ─────────────────────────────────────────────────────

export interface AutofixSafetyResult {
  safe: boolean;
  reason: string;
  blocked_path?: string;
  matched_keyword?: string;
}

/**
 * Full safety check: combines path check + keyword check.
 * Use this as the single entry point before any auto-fix attempt.
 *
 * @param filePath        The file path that would be modified
 * @param bugDescription  The bug title + description text
 */
export function isAutoFixSafe(
  filePath: string,
  bugDescription: string,
): AutofixSafetyResult {
  // 1. Path check
  const pathReason = blockedPathReason(filePath);
  if (pathReason) {
    return {
      safe: false,
      reason: `File "${filePath}" is in a protected directory (matched pattern: ${pathReason}). Manual review required.`,
      blocked_path: pathReason,
    };
  }

  // 2. Keyword check
  const safety = checkBugSafety(bugDescription);
  if (!safety.safe) {
    return {
      safe: false,
      reason: safety.reason,
      matched_keyword: safety.matched_keyword,
    };
  }

  return { safe: true, reason: 'Both path and keyword checks passed — auto-fix is permitted.' };
}
