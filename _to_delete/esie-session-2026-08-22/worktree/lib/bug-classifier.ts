/**
 * bug-classifier.ts — DEV-LOOP-2A
 * ─────────────────────────────────────────────────────────────────────────────
 * Given a Notion bug task (title + description), classifies whether it is safe
 * to auto-fix overnight without human review.
 *
 * Design principles:
 *   • CONSERVATIVE — prefers false-negative (mark not-fixable) over false-positive
 *   • Hard-coded keyword blocklist checked BEFORE the LLM call (zero-cost, no hallucination)
 *   • Uses Claude Haiku for cost efficiency (~$0.0003 per call)
 *   • Structured JSON output with confidence score for downstream gating
 *
 * Usage:
 *   const result = await classifyBug({ title: '...', description: '...' });
 *   if (result.auto_fixable && result.confidence > 0.8) { ... }
 *
 * Environment:
 *   ANTHROPIC_API_KEY — required at runtime
 * ─────────────────────────────────────────────────────────────────────────────
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export type FixCategory =
  | 'copy'           // Text copy, labels, placeholder text, typos
  | 'link'           // Broken or incorrect URLs / href attributes
  | 'css'            // Visual/layout bugs: spacing, colour, z-index, responsiveness
  | 'null-check'     // Crashes/errors when data is null/undefined/missing
  | 'static-content' // Missing or stale static data (city lists, country codes, etc.)
  | 'not-fixable';   // Anything touching auth, billing, migrations, PII, or unclear

export interface BugClassification {
  auto_fixable: boolean;
  confidence: number;       // 0.0 – 1.0
  reason: string;           // Human-readable explanation
  fix_category: FixCategory;
}

export interface BugInput {
  title: string;
  description: string;
}

// ─── Sensitive keyword blocklist ──────────────────────────────────────────────
// Checked BEFORE the LLM. Any match → immediate not-fixable.
// This is the safety net: the LLM prompt also enforces this, but belt-and-suspenders.

const SENSITIVE_KEYWORDS = [
  'auth', 'token', 'jwt', 'session', 'login', 'logout', 'sign-in', 'sign in',
  'password', 'passwd', 'credential', 'secret', 'api key', 'apikey',
  'billing', 'charge', 'payment', 'invoice', 'subscription', 'stripe', 'price',
  'migration', 'schema', 'alter table', 'drop table', 'foreign key', 'constraint',
  'pii', 'gdpr', 'personal data', 'email address', 'phone number', 'passport',
  'permission', 'role', 'access control', 'rbac', 'admin bypass', 'privilege',
  'sql injection', 'xss', 'csrf', 'security', 'vulnerability', 'exploit',
  'encryption', 'hash', 'certificate', 'ssl', 'tls',
];

function containsSensitiveKeyword(text: string): string | null {
  const lower = text.toLowerCase();
  for (const kw of SENSITIVE_KEYWORDS) {
    if (lower.includes(kw)) return kw;
  }
  return null;
}

// ─── System prompt ────────────────────────────────────────────────────────────

const SYSTEM_PROMPT = `You are a conservative bug-triage AI for the ReloPass relocation-management SaaS platform.

Your ONLY job is to decide whether a bug can be safely auto-fixed overnight by an AI coding assistant WITHOUT human review.

AUTO-FIXABLE categories (and ONLY these):
- copy: text typos, wrong labels, placeholder text, wrong button names
- link: broken URLs, wrong href values, 404 links
- css: visual bugs — wrong colour, spacing, z-index, layout on specific viewport
- null-check: crash when a field is null/undefined and the fix is a simple guard
- static-content: missing or stale static data (city list, country codes, enum values)

NOT AUTO-FIXABLE — reject immediately, no exceptions:
- Anything involving: authentication, tokens, sessions, passwords, credentials
- Anything involving: billing, payments, charges, subscriptions, pricing
- Anything involving: database migrations, schema changes, foreign keys
- Anything involving: PII, personal data, email addresses, GDPR
- Anything involving: security, permissions, access control, vulnerabilities
- Any bug where the root cause is unclear or involves business logic
- Any bug where the fix could affect multiple users or have cascading effects

RESPONSE FORMAT — respond with ONLY valid JSON, no markdown, no explanation:
{
  "auto_fixable": true | false,
  "confidence": 0.0 to 1.0,
  "reason": "one concise sentence explaining the decision",
  "fix_category": "copy" | "link" | "css" | "null-check" | "static-content" | "not-fixable"
}

CALIBRATION RULES:
- confidence > 0.85 only for crystal-clear, obviously trivial bugs
- confidence < 0.5 when you have any uncertainty
- When in doubt, set auto_fixable: false and fix_category: "not-fixable"
- A false negative (missing an auto-fixable bug) is ALWAYS safer than a false positive
- NEVER set auto_fixable: true if the bug mentions auth, token, password, billing, charge, payment, migration, schema, PII`;

// ─── Haiku API call ───────────────────────────────────────────────────────────

interface AnthropicMessage {
  role: 'user' | 'assistant';
  content: string;
}

async function callHaiku(messages: AnthropicMessage[], apiKey: string): Promise<string> {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 256,
      system: SYSTEM_PROMPT,
      messages,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Anthropic API error ${response.status}: ${body}`);
  }

  const data = await response.json() as { content: Array<{ type: string; text: string }> };
  const text = data.content?.[0]?.text ?? '';
  return text.trim();
}

// ─── JSON parser with fallback ────────────────────────────────────────────────

function parseClassification(raw: string): BugClassification {
  // Strip markdown code fences if present
  const cleaned = raw.replace(/^```(?:json)?\n?/m, '').replace(/\n?```$/m, '').trim();
  try {
    const parsed = JSON.parse(cleaned);
    return {
      auto_fixable: Boolean(parsed.auto_fixable),
      confidence: Math.max(0, Math.min(1, Number(parsed.confidence) || 0)),
      reason: String(parsed.reason || 'No reason provided'),
      fix_category: parsed.fix_category || 'not-fixable',
    };
  } catch {
    // JSON parse failed → conservative fallback
    return {
      auto_fixable: false,
      confidence: 0,
      reason: `Failed to parse classifier response: ${raw.slice(0, 100)}`,
      fix_category: 'not-fixable',
    };
  }
}

// ─── Main export ──────────────────────────────────────────────────────────────

/**
 * Classify a bug as auto-fixable or not.
 *
 * Safety guarantees:
 *   1. Keyword blocklist checked before LLM — any sensitive term → immediate rejection
 *   2. LLM prompt instructs conservative behaviour
 *   3. JSON parse failure → conservative not-fixable fallback
 *
 * @param bug     The bug title and description from Notion
 * @param apiKey  Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
 */
export async function classifyBug(
  bug: BugInput,
  apiKey?: string,
): Promise<BugClassification> {
  const key = apiKey ?? (typeof process !== 'undefined' ? process.env.ANTHROPIC_API_KEY : undefined)
    ?? (typeof Deno !== 'undefined' ? Deno.env.get('ANTHROPIC_API_KEY') : undefined);

  if (!key) {
    throw new Error('ANTHROPIC_API_KEY is required to run the bug classifier');
  }

  const combined = `${bug.title}\n${bug.description}`;

  // ── Hard blocklist check (before any LLM cost) ────────────────────────────
  const sensitiveMatch = containsSensitiveKeyword(combined);
  if (sensitiveMatch) {
    return {
      auto_fixable: false,
      confidence: 0.99,
      reason: `Blocked by sensitive keyword: "${sensitiveMatch}". Manual review required.`,
      fix_category: 'not-fixable',
    };
  }

  // ── LLM classification ────────────────────────────────────────────────────
  const userMessage = `Bug title: ${bug.title}\n\nBug description:\n${bug.description || '(no description provided)'}`;
  const raw = await callHaiku([{ role: 'user', content: userMessage }], key);
  const result = parseClassification(raw);

  // ── Post-LLM safety override: re-check in case LLM was fooled ─────────────
  if (result.auto_fixable) {
    const recheck = containsSensitiveKeyword(combined);
    if (recheck) {
      return {
        auto_fixable: false,
        confidence: 0.99,
        reason: `Safety override: LLM said fixable but blocklist matched "${recheck}".`,
        fix_category: 'not-fixable',
      };
    }
  }

  return result;
}
