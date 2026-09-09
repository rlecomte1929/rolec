/**
 * [P5-1] Tests for input_guardrails.ts
 *
 * Covers:
 *   - scanAndRedactPii: each PII type, combined, ordering (SSN before ID_NUMBER),
 *     false-positive avoidance, clean query passthrough
 *   - scanForEscalation: each keyword, multiple matches, case-insensitivity, clean query
 *   - runGuardrails: skip_topic_check=true path (no API call):
 *       clean query, PII only, escalation only, PII + escalation, audit logs
 *   - runGuardrails: topic_classifier integration (mocked):
 *       off_topic → safe=false, topic_rejection set
 *       borderline → safe=true, topic_clarification set
 *       hr_policy  → safe=true, no topic fields
 *   - ESCALATION_FOOTER constant content
 */

import { describe, it, expect, vi, afterEach } from 'vitest';

import {
  scanAndRedactPii,
  scanForEscalation,
  runGuardrails,
  ESCALATION_FOOTER,
  PII_PATTERNS,
} from '../input_guardrails';

// ---------------------------------------------------------------------------
// Module mock for topic_classifier — isolated from real API calls
// ---------------------------------------------------------------------------

vi.mock('../topic_classifier', () => ({
  REJECTION_MSG: 'I can only answer questions about your relocation policy and associated benefits. For other matters, please contact your HR Business Partner directly.',
  classifyQuery: vi.fn(),
}));

// We'll import classifyQuery after mocking to get the mock reference
import { classifyQuery, REJECTION_MSG } from '../topic_classifier';

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// 1. ESCALATION_FOOTER constant
// ---------------------------------------------------------------------------

describe('ESCALATION_FOOTER', () => {
  it('contains the required HR Business Partner phrasing', () => {
    expect(ESCALATION_FOOTER).toContain('HR Business Partner');
  });

  it('contains the published guidelines disclaimer', () => {
    expect(ESCALATION_FOOTER).toContain('published guidelines only');
  });

  it('is a non-empty string', () => {
    expect(typeof ESCALATION_FOOTER).toBe('string');
    expect(ESCALATION_FOOTER.length).toBeGreaterThan(10);
  });
});

// ---------------------------------------------------------------------------
// 2. PII_PATTERNS exports
// ---------------------------------------------------------------------------

describe('PII_PATTERNS', () => {
  it('exports all five required PII types', () => {
    expect(Object.keys(PII_PATTERNS)).toEqual(
      expect.arrayContaining(['PHONE', 'IBAN', 'PASSPORT', 'SSN', 'ID_NUMBER']),
    );
  });

  it('all patterns are RegExp instances', () => {
    for (const pattern of Object.values(PII_PATTERNS)) {
      expect(pattern).toBeInstanceOf(RegExp);
    }
  });
});

// ---------------------------------------------------------------------------
// 3. scanAndRedactPii
// ---------------------------------------------------------------------------

describe('scanAndRedactPii', () => {
  it('returns the original text unmodified when no PII is present', () => {
    const query = 'What is the housing allowance for a Manager in Norway?';
    const result = scanAndRedactPii(query);
    expect(result.sanitized).toBe(query);
    expect(result.detected_types).toHaveLength(0);
  });

  it('redacts a US SSN', () => {
    const result = scanAndRedactPii('My SSN is 123-45-6789 — can you help?');
    expect(result.sanitized).toContain('[SSN_REDACTED]');
    expect(result.sanitized).not.toContain('123-45-6789');
    expect(result.detected_types).toContain('SSN');
  });

  it('redacts an IBAN', () => {
    const result = scanAndRedactPii('Please reimburse to GB29NWBK60161331926819');
    expect(result.sanitized).toContain('[IBAN_REDACTED]');
    expect(result.sanitized).not.toContain('GB29NWBK60161331926819');
    expect(result.detected_types).toContain('IBAN');
  });

  it('redacts a passport number', () => {
    // Single-letter prefix avoids overlap with IBAN pattern (which needs 2 letters)
    const result = scanAndRedactPii('My passport is P12345678 and expires next year.');
    expect(result.sanitized).toContain('[PASSPORT_REDACTED]');
    expect(result.detected_types).toContain('PASSPORT');
  });

  it('redacts a phone number', () => {
    const result = scanAndRedactPii('Call me on +44 7700 900123 anytime.');
    expect(result.sanitized).toContain('[PHONE_REDACTED]');
    expect(result.sanitized).not.toContain('+44 7700 900123');
    expect(result.detected_types).toContain('PHONE');
  });

  it('redacts an 8-12 digit ID number', () => {
    const result = scanAndRedactPii('Employee ID 87654321 needs updating.');
    expect(result.sanitized).toContain('[ID_REDACTED]');
    expect(result.detected_types).toContain('ID_NUMBER');
  });

  it('redacts multiple PII types in the same query', () => {
    const query = 'My SSN is 123-45-6789 and my phone is +44 7700 900123.';
    const result = scanAndRedactPii(query);
    expect(result.detected_types).toContain('SSN');
    expect(result.detected_types).toContain('PHONE');
    expect(result.sanitized).not.toContain('123-45-6789');
    expect(result.sanitized).not.toContain('+44 7700 900123');
  });

  it('SSN takes priority over ID_NUMBER for overlapping patterns', () => {
    // "123-45-6789" should be caught as SSN, not ID_NUMBER
    const result = scanAndRedactPii('SSN: 123-45-6789');
    expect(result.detected_types).toContain('SSN');
    // SSN redaction happens first, so the digits are no longer available for ID_NUMBER
    expect(result.sanitized).toContain('[SSN_REDACTED]');
    expect(result.sanitized).not.toContain('[ID_REDACTED]');
  });

  it('is idempotent — re-scanning a sanitized string adds no new redactions', () => {
    const first = scanAndRedactPii('My SSN is 123-45-6789');
    const second = scanAndRedactPii(first.sanitized);
    expect(second.sanitized).toBe(first.sanitized);
    expect(second.detected_types).toHaveLength(0);
  });

  it('redacts multiple occurrences of the same PII type', () => {
    const result = scanAndRedactPii('IBAN1: DE89370400440532013000; IBAN2: FR7614508024004135979110');
    expect(result.detected_types).toContain('IBAN');
    expect(result.sanitized).not.toContain('DE89370400440532013000');
    expect(result.sanitized).not.toContain('FR7614508024004135979110');
  });

  it('does not redact a normal short number (below ID_NUMBER threshold)', () => {
    // A 4-digit amount like "2500" should not be caught by ID_NUMBER (\b\d{8,12}\b)
    const result = scanAndRedactPii('The allowance is EUR 2500 per month.');
    expect(result.detected_types).not.toContain('ID_NUMBER');
    expect(result.sanitized).toContain('2500');
  });
});

// ---------------------------------------------------------------------------
// 4. scanForEscalation
// ---------------------------------------------------------------------------

describe('scanForEscalation', () => {
  it('returns triggered=false when no escalation keywords are present', () => {
    const result = scanForEscalation('What is the housing allowance for my grade?');
    expect(result.triggered).toBe(false);
    expect(result.matched_keywords).toHaveLength(0);
  });

  it('detects "i was promised"', () => {
    const result = scanForEscalation('I was promised a higher allowance in my offer letter.');
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain('i was promised');
  });

  it('detects "my contract says"', () => {
    const result = scanForEscalation('But my contract says I get EUR 4,000 a month.');
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain('my contract says');
  });

  it('detects "want to escalate"', () => {
    const result = scanForEscalation("I want to escalate this issue.");
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain('want to escalate');
  });

  it('detects "i\'m entitled to"', () => {
    const result = scanForEscalation("I'm entitled to relocation support.");
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain("i'm entitled to");
  });

  it('detects "they told me"', () => {
    const result = scanForEscalation('They told me the policy was different.');
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain('they told me');
  });

  it('detects "legal action"', () => {
    const result = scanForEscalation('I am considering legal action if this is not resolved.');
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain('legal action');
  });

  it('detects "dispute"', () => {
    const result = scanForEscalation('I want to raise a dispute about my lump sum.');
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain('dispute');
  });

  it('is case-insensitive', () => {
    const result = scanForEscalation('I WAS PROMISED additional support.');
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain('i was promised');
  });

  it('detects multiple keywords in a single query', () => {
    const result = scanForEscalation(
      "My contract says EUR 5000 and I was promised extra support.",
    );
    expect(result.triggered).toBe(true);
    expect(result.matched_keywords).toContain('my contract says');
    expect(result.matched_keywords).toContain('i was promised');
    expect(result.matched_keywords.length).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// 5. runGuardrails — skip_topic_check=true (no API, no mock needed)
// ---------------------------------------------------------------------------

describe('runGuardrails (skip_topic_check=true)', () => {
  it('returns safe=true for a clean query with no PII or escalation', async () => {
    const result = await runGuardrails(
      'What is the housing allowance for a Senior Manager moving to Norway?',
      { skip_topic_check: true },
    );
    expect(result.safe).toBe(true);
    expect(result.pii_detected).toBe(false);
    expect(result.pii_types).toHaveLength(0);
    expect(result.escalation_triggered).toBe(false);
    expect(result.escalation_footer).toBeUndefined();
    expect(result.topic_rejection).toBeUndefined();
    expect(result.topic_clarification).toBeUndefined();
  });

  it('sanitizes PII and sets pii_detected=true', async () => {
    const result = await runGuardrails(
      'My SSN is 123-45-6789. What allowance do I get?',
      { skip_topic_check: true },
    );
    expect(result.pii_detected).toBe(true);
    expect(result.pii_types).toContain('SSN');
    expect(result.sanitized_query).not.toContain('123-45-6789');
    expect(result.sanitized_query).toContain('[SSN_REDACTED]');
    expect(result.safe).toBe(true); // PII alone doesn't block the query
  });

  it('sets escalation_triggered=true and attaches escalation_footer', async () => {
    const result = await runGuardrails(
      'My contract says I should get more — I want to escalate this.',
      { skip_topic_check: true },
    );
    expect(result.escalation_triggered).toBe(true);
    expect(result.escalation_footer).toBe(ESCALATION_FOOTER);
    expect(result.safe).toBe(true); // escalation does not block the query
  });

  it('handles PII + escalation simultaneously', async () => {
    const result = await runGuardrails(
      'My SSN is 123-45-6789 and my contract says I get more.',
      { skip_topic_check: true },
    );
    expect(result.pii_detected).toBe(true);
    expect(result.escalation_triggered).toBe(true);
    expect(result.escalation_footer).toBe(ESCALATION_FOOTER);
    expect(result.sanitized_query).not.toContain('123-45-6789');
    expect(result.safe).toBe(true);
  });

  it('sets query_hash to "skipped" when skip_topic_check is true', async () => {
    const result = await runGuardrails('Any question', { skip_topic_check: true });
    expect(result.query_hash).toBe('skipped');
  });

  it('does not call classifyQuery when skip_topic_check=true', async () => {
    await runGuardrails('Any question', { skip_topic_check: true });
    expect(classifyQuery).not.toHaveBeenCalled();
  });

  it('includes session_id in audit output (log captured via spy)', async () => {
    const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    await runGuardrails('My contract says something.', {
      skip_topic_check: true,
      session_id: 'test-session-42',
    });
    const logs = consoleSpy.mock.calls.map((c) => c.join(' '));
    expect(logs.some((l) => l.includes('test-session-42'))).toBe(true);
    consoleSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// 6. runGuardrails — topic_classifier integration (mocked)
// ---------------------------------------------------------------------------

describe('runGuardrails (with mocked topic_classifier)', () => {
  it('sets safe=false and topic_rejection when classifier returns off_topic', async () => {
    vi.mocked(classifyQuery).mockResolvedValueOnce({
      category: 'off_topic',
      confidence: 0.97,
      rejection_reason: REJECTION_MSG,
      query_hash: 'abc12345',
      latency_ms: 42,
    });

    const result = await runGuardrails("What's the best restaurant in Oslo?");
    expect(result.safe).toBe(false);
    expect(result.topic_rejection).toBe(REJECTION_MSG);
    expect(result.topic_clarification).toBeUndefined();
    expect(result.query_hash).toBe('abc12345');
  });

  it('sets safe=true and topic_clarification when classifier returns borderline', async () => {
    vi.mocked(classifyQuery).mockResolvedValueOnce({
      category: 'borderline',
      confidence: 0.62,
      clarification_prompt: "I can tell you what your relocation policy says about remote work. Is that what you're looking for?",
      query_hash: 'def67890',
      latency_ms: 55,
    });

    const result = await runGuardrails('Can I work from home after the move?');
    expect(result.safe).toBe(true);
    expect(result.topic_clarification).toContain('remote work');
    expect(result.topic_rejection).toBeUndefined();
  });

  it('sets safe=true with no topic fields when classifier returns hr_policy', async () => {
    vi.mocked(classifyQuery).mockResolvedValueOnce({
      category: 'hr_policy',
      confidence: 0.99,
      query_hash: 'ghi11223',
      latency_ms: 30,
    });

    const result = await runGuardrails('What is the housing allowance for a Director?');
    expect(result.safe).toBe(true);
    expect(result.topic_rejection).toBeUndefined();
    expect(result.topic_clarification).toBeUndefined();
  });

  it('passes the sanitized (PII-redacted) query to the classifier', async () => {
    vi.mocked(classifyQuery).mockResolvedValueOnce({
      category: 'hr_policy',
      confidence: 0.95,
      query_hash: 'aaa00001',
      latency_ms: 28,
    });

    await runGuardrails('My SSN is 123-45-6789. What is my housing allowance?');
    const passedQuery = vi.mocked(classifyQuery).mock.calls[0][0];
    expect(passedQuery).not.toContain('123-45-6789');
    expect(passedQuery).toContain('[SSN_REDACTED]');
  });

  it('escalation does not block an hr_policy query — both safe=true and footer attached', async () => {
    vi.mocked(classifyQuery).mockResolvedValueOnce({
      category: 'hr_policy',
      confidence: 0.88,
      query_hash: 'bbb00002',
      latency_ms: 35,
    });

    const result = await runGuardrails(
      'My contract says I get more. What does the policy say about housing allowance?',
    );
    expect(result.safe).toBe(true);
    expect(result.escalation_triggered).toBe(true);
    expect(result.escalation_footer).toBe(ESCALATION_FOOTER);
    expect(result.topic_rejection).toBeUndefined();
  });

  it('uses rejection_reason from classifier response when available', async () => {
    const customRejection = 'Custom rejection from classifier';
    vi.mocked(classifyQuery).mockResolvedValueOnce({
      category: 'off_topic',
      confidence: 0.98,
      rejection_reason: customRejection,
      query_hash: 'ccc00003',
      latency_ms: 25,
    });

    const result = await runGuardrails('Tell me about the Champions League.');
    expect(result.topic_rejection).toBe(customRejection);
  });

  it('falls back to REJECTION_MSG when rejection_reason is missing', async () => {
    vi.mocked(classifyQuery).mockResolvedValueOnce({
      category: 'off_topic',
      confidence: 0.95,
      // rejection_reason intentionally omitted
      query_hash: 'ddd00004',
      latency_ms: 22,
    });

    const result = await runGuardrails('Some off topic thing.');
    expect(result.topic_rejection).toBe(REJECTION_MSG);
  });
});
