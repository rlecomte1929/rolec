/**
 * [P4-5] assistant_router.ts — Orchestration layer for the AI policy assistant
 *
 * Implements the full query pipeline with fast-fail paths at each stage.
 * Fast refusals (no LLM call) are always preferable to slow hallucinations.
 *
 * Decision tree:
 *   processQuery(query, employeeId)
 *     ├─ topic_classifier(query)
 *     │   ├─ off_topic → return TOPIC_REJECTION_MSG   [no retrieval, no LLM]
 *     │   └─ hr_policy | borderline → continue
 *     ├─ retrieve_policy(query, tier, company_id)
 *     │   └─ top_score < 0.65 → return LOW_CONFIDENCE_MSG  [no LLM call]
 *     ├─ check_policy_expiry(company_id)
 *     │   └─ expired → return POLICY_EXPIRED_MSG     [no LLM call]
 *     ├─ generate_response(query, chunks)             [LLM call]
 *     └─ faithfulness_check(response, chunks)
 *         ├─ pass → return response with chunk citations
 *         └─ fail → return raw excerpts              [no further LLM call]
 *
 * Fallback contract:
 *   - All fallback strings are hardcoded constants — NEVER LLM-generated
 *   - Every fallback path logs a FallbackReason code for observability
 *   - Responses always include latency_ms for SLA monitoring
 *
 * Generation model:
 *   Claude claude-haiku-4-5-20251001, temperature=0 (deterministic), grounded system prompt.
 *   The system prompt strictly forbids extrapolation beyond the retrieved context.
 *
 * Policy expiry:
 *   Queries the policy_documents table for the company. If no approved document
 *   exists, or the most recent effective_date is older than POLICY_MAX_AGE_DAYS,
 *   the policy is treated as expired and the POLICY_EXPIRED_MSG is returned.
 */

import { classifyQuery } from './topic_classifier';
import type { FallbackReason } from './topic_classifier';
import { retrievePolicy } from './retrieve_policy';
import type { PolicyChunk } from './retrieve_policy';
import { runOutputGuardrails } from './output_guardrails';
import { runGuardrails } from './input_guardrails';
import { logger } from '../../lib/logger';

// Re-export so consumers have a single import point
export type { FallbackReason };

// ---------------------------------------------------------------------------
// Hardcoded fallback strings — NEVER LLM-generated
// ---------------------------------------------------------------------------

export const LOW_CONFIDENCE_MSG =
  'I was not able to find a relevant section of your company policy for this question. ' +
  'Please contact your HR administrator.';

export const POLICY_EXPIRED_MSG =
  'Your company policy is currently under review. Please contact HR for current guidance.';

export const TOPIC_REJECTION_MSG =
  'I can only answer questions about your relocation policy and associated benefits. ' +
  'For other matters, please contact your HR Business Partner directly.';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * Minimum RRF score required for at least one retrieved chunk to proceed.
 * If the top chunk scores below this threshold, context is too weak for
 * reliable generation and a LOW_CONFIDENCE refusal is returned immediately.
 */
export const MIN_RRF_SCORE = 0.65;

/**
 * Maximum age (in days) for a policy document before it is considered
 * expired. Documents whose effective_date is older than this are treated
 * as stale. Default: 730 days (2 years).
 */
export const POLICY_MAX_AGE_DAYS = 730;

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export type AssistantAnswerType = 'generated' | 'raw_excerpt' | 'refusal';

export interface AssistantResponse {
  /** Text shown to the employee */
  answer_text: string;
  /** Rendering hint for the UI */
  answer_type: AssistantAnswerType;
  /** Set on all fallback paths for logging and analytics */
  fallback_reason?: FallbackReason;
  /** Retrieved chunks — present when retrieval succeeded */
  chunks?: PolicyChunk[];
  /** NLI faithfulness score (0–1) — present when generation ran */
  faithfulness_score?: number;
  /** Total pipeline latency in milliseconds */
  latency_ms: number;
}

// ---------------------------------------------------------------------------
// Lazy Supabase import (same pattern as retrieve_policy.ts)
// Allows this module to be imported in test environments without Supabase env vars.
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function getSupabase(): Promise<any> {
  const { supabase } = await import('../../lib/supabase');
  return supabase;
}

// ---------------------------------------------------------------------------
// Step 3: Policy expiry check
// ---------------------------------------------------------------------------

/**
 * Returns true if the company's policy is considered expired or unavailable.
 *
 * Checks policy_documents for the company and verifies:
 *   (a) At least one document has processing_status = 'approved'
 *   (b) Its effective_date is within the POLICY_MAX_AGE_DAYS window
 *
 * If there is no approved document, or the most recent is older than
 * POLICY_MAX_AGE_DAYS, the policy is considered expired.
 */
export async function isPolicyExpired(companyId: string): Promise<boolean> {
  try {
    const supabase = await getSupabase();
    const { data, error } = await supabase
      .from('policy_documents')
      .select('effective_date, processing_status')
      .eq('company_id', companyId)
      .eq('processing_status', 'approved')
      .order('effective_date', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error || !data) {
      logger.warn(`[assistant_router] Policy expiry check failed for company=${companyId}: no approved document`);
      return true; // no approved document → treat as expired
    }

    if (!data.effective_date) {
      // No date set → assume valid (don't block due to missing metadata)
      return false;
    }

    const thresholdDate = new Date();
    thresholdDate.setDate(thresholdDate.getDate() - POLICY_MAX_AGE_DAYS);
    const effectiveDate = new Date(data.effective_date);
    const expired = effectiveDate < thresholdDate;

    if (expired) {
      logger.warn(
        `[assistant_router] Policy expired for company=${companyId}: effective_date=${data.effective_date}`,
      );
    }
    return expired;
  } catch (err) {
    logger.error('[assistant_router] isPolicyExpired threw:', err);
    return true; // fail-safe: treat as expired if check errors
  }
}

// ---------------------------------------------------------------------------
// Step 4: Response generation
// ---------------------------------------------------------------------------

/**
 * Grounded system prompt for the generation step.
 * The model is strictly forbidden from extrapolating beyond the provided context.
 */
const GENERATION_SYSTEM_PROMPT = `You are a precise HR policy assistant for a corporate relocation programme.

RULES:
1. Answer using ONLY the information in the POLICY CONTEXT below. Never add, infer, or extrapolate.
2. If the context does not contain enough information, say: "The policy does not specify this. Please contact HR."
3. Keep answers concise, factual, and in plain English.
4. After each factual claim, add a source citation in the format [Source: <section_path>].
5. Never mention confidence levels, model names, or technical details.
6. Never contradict or reinterpret the context — quote it directly where possible.`;

/**
 * Generate a grounded response for the query using the retrieved policy chunks.
 *
 * Uses Claude Haiku at temperature=0 for deterministic, fast generation.
 * The prompt strictly grounds the model in the retrieved context.
 *
 * @param query         The employee's query
 * @param chunks        Retrieved policy chunks used as context
 * @param anthropicKey  Anthropic API key
 * @param apiBase       API base URL (override for tests)
 */
export async function generateResponse(
  query: string,
  chunks: PolicyChunk[],
  anthropicKey: string,
  apiBase = 'https://api.anthropic.com',
): Promise<string> {
  const context = chunks
    .map(
      (c, i) =>
        `[Chunk ${i + 1}] ${c.section_path ? `(${c.section_path}) ` : ''}${c.text.slice(0, 600)}`,
    )
    .join('\n\n');

  const userMessage = `POLICY CONTEXT:\n${context}\n\nEMPLOYEE QUESTION: ${query}`;

  const response = await fetch(`${apiBase}/v1/messages`, {
    method: 'POST',
    headers: {
      'x-api-key': anthropicKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 600,
      temperature: 0,
      system: GENERATION_SYSTEM_PROMPT,
      messages: [{ role: 'user', content: userMessage }],
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`assistant_router: generation API error ${response.status}: ${body}`);
  }

  const apiResponse = (await response.json()) as {
    content: Array<{ type: string; text: string }>;
  };

  const text = apiResponse.content.find((c) => c.type === 'text')?.text?.trim() ?? '';
  if (!text) throw new Error('assistant_router: generation returned empty response');
  return text;
}

// ---------------------------------------------------------------------------
// Step 4b: Raw excerpt fallback
// ---------------------------------------------------------------------------

/**
 * Build a raw excerpt response from retrieved chunks when faithfulness fails.
 * Returns the top chunks as labelled quoted excerpts — guaranteed faithful.
 */
export function buildRawExcerptResponse(chunks: PolicyChunk[]): string {
  const excerpts = chunks
    .slice(0, 3) // top 3 chunks only
    .map((c, i) => {
      const label = c.section_path ?? `Policy excerpt ${i + 1}`;
      return `**${label}:**\n> ${c.text.slice(0, 400).trim()}`;
    })
    .join('\n\n');

  return (
    'Here are the most relevant sections from your company policy:\n\n' +
    excerpts +
    '\n\n_This excerpt was retrieved directly from your policy document without AI rephrasing._'
  );
}

// ---------------------------------------------------------------------------
// Employee profile resolution
// ---------------------------------------------------------------------------

interface EmployeeProfile {
  company_id: string;
  employee_tier: string;
}

/**
 * Resolve employee_tier and company_id for a given employeeId.
 * Throws if the profile cannot be found.
 */
async function resolveEmployeeProfile(employeeId: string): Promise<EmployeeProfile> {
  const supabase = await getSupabase();
  const { data, error } = await supabase
    .from('profiles')
    .select('company_id, employee_tier')
    .eq('id', employeeId)
    .single();

  if (error || !data) {
    throw new Error(`assistant_router: could not resolve profile for employeeId=${employeeId}`);
  }

  return {
    company_id: data.company_id as string,
    employee_tier: (data.employee_tier as string | null) ?? 'All',
  };
}

// ---------------------------------------------------------------------------
// Main: processQuery
// ---------------------------------------------------------------------------

export interface ProcessQueryOptions {
  /** Override API key for testability */
  anthropicKey?: string;
  /** Override API base URL for tests */
  apiBase?: string;
  /** Override retrieval k (default 5) */
  k?: number;
}

/**
 * Process an employee query through the full AI assistant pipeline.
 *
 * All fallback paths return immediately without proceeding further.
 * Fallback reasons are logged to console for observability (structured
 * logging integration is the responsibility of the calling layer).
 *
 * @param query       Raw employee query string
 * @param employeeId  Employee's Supabase auth user ID
 * @param options     Optional overrides for testing
 */
export async function processQuery(
  query: string,
  employeeId: string,
  options: ProcessQueryOptions = {},
): Promise<AssistantResponse> {
  const t0 = Date.now();
  const {
    apiBase = 'https://api.anthropic.com',
    k = 5,
  } = options;

  const apiKey =
    options.anthropicKey ??
    (typeof import.meta !== 'undefined'
      ? (import.meta.env?.VITE_ANTHROPIC_API_KEY as string | undefined)
      : process.env.ANTHROPIC_API_KEY);

  // ── Step 0: Input guardrails (PII masking, escalation detection) ─────────
  // Must run BEFORE any LLM call. Uses the sanitized query for all downstream steps.

  const guardrailResult = await runGuardrails(query, {
    anthropic_key: apiKey,
    skip_topic_check: true, // topic classification handled in Step 1 below
  });

  // If guardrails hard-reject the query (off-topic or unsafe), return immediately
  if (!guardrailResult.safe && guardrailResult.topic_rejection) {
    const reason: FallbackReason = 'TOPIC_REJECTED';
    logger.log(
      `[assistant_router] GUARDRAIL_REJECT reason=${reason} hash=${guardrailResult.query_hash}`,
    );
    return {
      answer_text: guardrailResult.topic_rejection,
      answer_type: 'refusal',
      fallback_reason: reason,
      latency_ms: Date.now() - t0,
    };
  }

  // Use sanitized (PII-stripped) query for all downstream pipeline steps
  const safeQuery = guardrailResult.sanitized_query;

  // ── Step 1: Topic classification ─────────────────────────────────────────

  const classification = await classifyQuery(safeQuery, apiKey);

  if (classification.category === 'off_topic') {
    const reason: FallbackReason = 'TOPIC_REJECTED';
    logger.log(
      `[assistant_router] FALLBACK reason=${reason} hash=${classification.query_hash}`,
    );
    return {
      answer_text: TOPIC_REJECTION_MSG,
      answer_type: 'refusal',
      fallback_reason: reason,
      latency_ms: Date.now() - t0,
    };
  }

  // ── Resolve employee profile (needed for retrieval) ───────────────────────

  const profile = await resolveEmployeeProfile(employeeId);

  // ── Step 2: Policy retrieval ──────────────────────────────────────────────

  const retrievalResult = await retrievePolicy({
    query: safeQuery,
    employee_tier: profile.employee_tier,
    company_id: profile.company_id,
    k,
  });

  const chunks = retrievalResult.chunks;
  const topScore = chunks.length > 0 ? chunks[0].rrf_score : 0;

  if (topScore < MIN_RRF_SCORE || chunks.length === 0) {
    const reason: FallbackReason = 'LOW_CONFIDENCE';
    logger.log(
      `[assistant_router] FALLBACK reason=${reason} top_rrf=${topScore.toFixed(3)} company=${profile.company_id}`,
    );
    return {
      answer_text: LOW_CONFIDENCE_MSG,
      answer_type: 'refusal',
      fallback_reason: reason,
      latency_ms: Date.now() - t0,
    };
  }

  // ── Step 3: Policy expiry check ───────────────────────────────────────────

  const expired = await isPolicyExpired(profile.company_id);

  if (expired) {
    const reason: FallbackReason = 'POLICY_EXPIRED';
    logger.log(
      `[assistant_router] FALLBACK reason=${reason} company=${profile.company_id}`,
    );
    return {
      answer_text: POLICY_EXPIRED_MSG,
      answer_type: 'refusal',
      fallback_reason: reason,
      chunks,
      latency_ms: Date.now() - t0,
    };
  }

  // ── Step 4: Generate response ─────────────────────────────────────────────

  if (!apiKey) {
    // No API key: serve raw excerpts (safer than no response)
    logger.warn('[assistant_router] No API key — serving raw excerpt fallback');
    const reason: FallbackReason = 'FAITHFULNESS_FAIL';
    return {
      answer_text: buildRawExcerptResponse(chunks),
      answer_type: 'raw_excerpt',
      fallback_reason: reason,
      chunks,
      latency_ms: Date.now() - t0,
    };
  }

  const generatedText = await generateResponse(safeQuery, chunks, apiKey, apiBase);

  // ── Step 5: Output guardrails (cross-tier fence + faithfulness hard-block) ─
  //
  // Runs after every generation. On REGENERATE, one retry is attempted.
  // Second failure on any check → serve raw excerpts immediately.

  const sessionId = `${employeeId}-${t0}`;

  const guardrailCheck1 = await runOutputGuardrails(
    generatedText,
    chunks,
    profile.employee_tier,
    apiKey,
    apiBase,
    sessionId,
  );

  if (guardrailCheck1.action === 'SERVE_RAW') {
    const reason: FallbackReason = 'FAITHFULNESS_FAIL';
    logger.log(
      `[assistant_router] FALLBACK reason=${reason}` +
        ` faithfulness=${guardrailCheck1.faithfulness_score}` +
        ` session=${sessionId}`,
    );
    return {
      answer_text: buildRawExcerptResponse(chunks),
      answer_type: 'raw_excerpt',
      fallback_reason: reason,
      chunks,
      faithfulness_score: guardrailCheck1.faithfulness_score,
      latency_ms: Date.now() - t0,
    };
  }

  if (guardrailCheck1.action === 'REGENERATE') {
    // Cross-tier leak detected — attempt one regeneration
    const reason: FallbackReason = 'FAITHFULNESS_FAIL';
    logger.warn(
      `[assistant_router] CROSS_TIER_DETECTED — regenerating session=${sessionId}` +
        ` leaks=${guardrailCheck1.leaks?.length}`,
    );

    const regeneratedText = await generateResponse(safeQuery, chunks, apiKey, apiBase);

    const guardrailCheck2 = await runOutputGuardrails(
      regeneratedText,
      chunks,
      profile.employee_tier,
      apiKey,
      apiBase,
      `${sessionId}-retry`,
    );

    if (guardrailCheck2.action !== 'PASS') {
      // Second failure → serve raw excerpts (never return a potentially leaky response)
      logger.warn(
        `[assistant_router] OUTPUT_GUARDRAIL_DOUBLE_FAIL — serving raw excerpt session=${sessionId}`,
      );
      return {
        answer_text: buildRawExcerptResponse(chunks),
        answer_type: 'raw_excerpt',
        fallback_reason: reason,
        chunks,
        faithfulness_score: guardrailCheck2.faithfulness_score,
        latency_ms: Date.now() - t0,
      };
    }

    // Regeneration passed — use regenerated text
    const finalRegenText = guardrailResult.escalation_footer
      ? `${regeneratedText}\n\n${guardrailResult.escalation_footer}`
      : regeneratedText;

    logger.log(
      `[assistant_router] OK (after regeneration) faithfulness=${guardrailCheck2.faithfulness_score}` +
        ` chunks=${chunks.length} latency=${Date.now() - t0}ms session=${sessionId}`,
    );

    return {
      answer_text: finalRegenText,
      answer_type: 'generated',
      chunks,
      faithfulness_score: guardrailCheck2.faithfulness_score,
      latency_ms: Date.now() - t0,
    };
  }

  // ── Happy path: original response passed all guardrails ───────────────────

  logger.log(
    `[assistant_router] OK faithfulness=${guardrailCheck1.faithfulness_score}` +
      ` chunks=${chunks.length} latency=${Date.now() - t0}ms`,
  );

  // Append escalation footer if input guardrails detected dispute language
  const finalText = guardrailResult.escalation_footer
    ? `${generatedText}\n\n${guardrailResult.escalation_footer}`
    : generatedText;

  return {
    answer_text: finalText,
    answer_type: 'generated',
    chunks,
    faithfulness_score: guardrailCheck1.faithfulness_score,
    latency_ms: Date.now() - t0,
  };
}
