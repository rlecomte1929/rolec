/**
 * Domain router for the unified relocation assistant (Slice 5 — policy bridge).
 *
 * Decides whether a free-text question is about IMMIGRATION (visas/permits/
 * documents → the immigration RAG) or COMPANY POLICY (benefits/allowances/
 * coverage → the policy RAG), or is genuinely AMBIGUOUS (→ ask the user).
 *
 * Deterministic weighted keyword scoring (mirrors the style of the backend
 * `score_policy_assistant_topics`). It is intentionally biased so that
 * coverage-INTENT phrases ("does my company pay for…", "is X covered") outweigh
 * a bare immigration noun — because "does my company pay for the visa?" is a
 * policy question. A misroute is bounded: each engine still grounds/refuses, so
 * the worst case is the wrong engine declining, not a wrong answer.
 */
export type AssistantDomain = 'immigration' | 'policy' | 'ambiguous';

type Signal = [phrase: string, weight: number];

const IMMIGRATION_SIGNALS: Signal[] = [
  ['visa', 2], ['permit', 2], ['passport', 2], ['apostille', 2], ['biometric', 2],
  ['anabin', 2], ['blue card', 2], ['residence', 2], ['register', 2], ['registration', 2],
  ['embassy', 2], ['consulate', 2], ['immigration', 2], ['processing time', 2],
  ['document', 1], ['appointment', 1],
];

const POLICY_SIGNALS: Signal[] = [
  ['my company', 3], ['my employer', 3], ['pay for', 3], ['covered', 3], ['cover', 3],
  ['reimburse', 3], ['allowance', 3], ['benefit', 3], ['entitled', 3], ['relocation package', 3],
  ['employer', 2], ['budget', 2], ['housing', 2], ['accommodation', 2], ['flight', 2],
  ['home leave', 2], ['school', 2], ['cola', 2], ['shipping', 2], ['spouse support', 2],
  ['tax equalization', 2], ['tax equalisation', 2],
];

function score(haystack: string, signals: Signal[]): number {
  let total = 0;
  for (const [phrase, weight] of signals) {
    if (haystack.includes(phrase)) total += weight;
  }
  return total;
}

export function classifyAssistantDomain(question: string): AssistantDomain {
  const q = (question || '').toLowerCase();
  const immigration = score(q, IMMIGRATION_SIGNALS);
  const policy = score(q, POLICY_SIGNALS);

  if (immigration === 0 && policy === 0) return 'ambiguous';
  if (immigration === policy) return 'ambiguous';
  return immigration > policy ? 'immigration' : 'policy';
}
