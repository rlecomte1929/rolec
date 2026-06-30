import { useState } from 'react';
import { Alert, Badge, Button, Card, Input } from '../../components/antigravity';
import {
  askImmigrationQuestion,
  type ImmigrationAnswer,
} from '../../api/immigrationAnswer';
import { getPolicyAnswer } from '../../api/policyAssistantQuery';
import type { PolicyAssistantAnswer } from '../../types/policyAssistant';
import {
  deriveSupportStatus,
  supportStatusLabel,
  supportStatusBadgeClass,
} from '../policy/employeePolicyAssistantModel';
import { submitAiFeedback, type FeedbackVerdict } from '../../api/aiFeedback';
import { routeAssistantDomain, type AssistantDomain } from '../../api/assistantRoute';

/**
 * Unified relocation assistant (Slice 5 — policy bridge). One question box that
 * routes each question to the grounded IMMIGRATION engine ("what does my move
 * need") or the company-POLICY engine ("what does my company cover"), and asks
 * the user when the question is genuinely ambiguous. Each engine keeps its own
 * grounding + citations + refusal, so a misroute is bounded (the wrong engine
 * just declines). Immigration 👍/👎 still feeds ai_human_feedback (AIQ-856).
 */

type ConfidenceBadge = { label: string; variant: 'success' | 'info' | 'warning' | 'neutral' };

function confidenceBadge(confidence?: string | null): ConfidenceBadge {
  switch ((confidence || '').toLowerCase()) {
    case 'high': return { label: 'High confidence', variant: 'success' };
    case 'medium': return { label: 'Medium confidence', variant: 'info' };
    case 'low': return { label: 'Low confidence', variant: 'warning' };
    default: return { label: 'Confidence: unknown', variant: 'neutral' };
  }
}

export function ImmigrationAnswerPanel() {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [nationality, setNationality] = useState('');
  const [permitType, setPermitType] = useState('');
  const [query, setQuery] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<ImmigrationAnswer | null>(null);
  const [policyAnswer, setPolicyAnswer] = useState<PolicyAssistantAnswer | null>(null);
  const [clarifyFor, setClarifyFor] = useState<string | null>(null);

  const [verdict, setVerdict] = useState<FeedbackVerdict | null>(null);
  const [verdictError, setVerdictError] = useState(false);

  const canAsk = !!query.trim();
  const corridorComplete = !!(from.trim() && to.trim() && nationality.trim() && permitType.trim());

  function resetAnswers() {
    setError(null);
    setAnswer(null);
    setPolicyAnswer(null);
    setVerdict(null);
    setVerdictError(false);
  }

  async function ask(forced?: AssistantDomain) {
    const q = query.trim();
    if (!q) return;
    resetAnswers();
    // Route via the canonical backend classifier; a routing failure is treated as
    // ambiguous so the user disambiguates rather than getting a silent misroute.
    let domain: AssistantDomain;
    if (forced) {
      domain = forced;
    } else {
      try {
        domain = await routeAssistantDomain(q);
      } catch {
        domain = 'ambiguous';
      }
    }

    if (domain === 'ambiguous') {
      setClarifyFor(q);
      return;
    }
    setClarifyFor(null);

    if (domain === 'immigration') {
      if (!corridorComplete) {
        setError('Add your corridor (From / To / Nationality / Permit) above for immigration questions.');
        return;
      }
      setLoading(true);
      try {
        const res = await askImmigrationQuestion({
          corridor_from: from.trim().toUpperCase(),
          corridor_to: to.trim().toUpperCase(),
          nationality: nationality.trim().toUpperCase(),
          permit_type: permitType.trim(),
          query: q,
        });
        setAnswer(res);
      } catch {
        setError('Could not get an answer right now. Please try again.');
      } finally {
        setLoading(false);
      }
    } else {
      setLoading(true);
      try {
        const res = await getPolicyAnswer(q);
        setPolicyAnswer(res);
      } catch {
        setError('Could not get an answer right now. Please try again.');
      } finally {
        setLoading(false);
      }
    }
  }

  async function rate(v: FeedbackVerdict) {
    if (!answer?.trace_id || verdict) return;
    setVerdict(v); // optimistic
    setVerdictError(false);
    try {
      await submitAiFeedback({ trace_session_id: answer.trace_id, verdict: v });
    } catch {
      setVerdict(null);
      setVerdictError(true);
    }
  }

  const isRefusal = !!answer && answer.answer_kind !== 'answer';
  const conf = confidenceBadge(answer?.confidence);
  const policyStatus = policyAnswer ? deriveSupportStatus(policyAnswer) : null;

  return (
    <div className="max-w-3xl space-y-4">
      <Card>
        <div className="space-y-3 p-1">
          <p className="text-sm text-slate-600">
            Ask about <strong>your move</strong> (visas, permits, documents) or <strong>your company&apos;s
            benefits</strong> (allowances, what&apos;s covered). Both answers are grounded and cite where each
            point comes from.
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Input aria-label="From country" placeholder="From (e.g. IN)" value={from} onChange={(v) => setFrom(v)} />
            <Input aria-label="To country" placeholder="To (e.g. DE)" value={to} onChange={(v) => setTo(v)} />
            <Input aria-label="Nationality" placeholder="Nationality (e.g. IN)" value={nationality} onChange={(v) => setNationality(v)} />
            <Input aria-label="Permit type" placeholder="Permit (e.g. work)" value={permitType} onChange={(v) => setPermitType(v)} />
          </div>
          <textarea
            aria-label="Your question"
            className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 placeholder-gray-300 focus:outline-none focus:ring-1 focus:ring-accent-500"
            rows={3}
            placeholder="e.g. What documents do I need? · Does my company cover temporary housing?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="flex items-center gap-3">
            <Button variant="primary" onClick={() => void ask()} disabled={!canAsk || loading}>
              {loading ? 'Asking…' : 'Ask'}
            </Button>
            <span className="text-xs text-gray-400">Grounded + cited · always confirm with the cited source</span>
          </div>
        </div>
      </Card>

      {error && <Alert variant="error">{error}</Alert>}

      {clarifyFor && (
        <Card>
          <div className="space-y-2 p-1" data-testid="assistant-clarifier">
            <p className="text-sm text-slate-700">
              Is this about <strong>your move</strong>, or <strong>your company&apos;s benefits</strong>?
            </p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void ask('immigration')}>About my move</Button>
              <Button variant="outline" onClick={() => void ask('policy')}>About my benefits</Button>
            </div>
          </div>
        </Card>
      )}

      {answer && (
        <Card>
          <div className="space-y-3 p-1" data-testid="immigration-answer">
            {isRefusal ? (
              <Alert variant="warning">
                We don&apos;t have enough official, corridor-specific source material to answer
                that confidently yet. Please confirm with the relevant authority.
              </Alert>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <Badge variant="neutral">Immigration guidance</Badge>
                  <Badge variant={conf.variant}>{conf.label}</Badge>
                  {answer.all_stale_warning && <Badge variant="warning">Sources may be outdated</Badge>}
                </div>
                <div className="whitespace-pre-wrap text-sm text-slate-800">{answer.answer_text}</div>
                {answer.cited_sources?.length > 0 && (
                  <div className="border-t border-gray-100 pt-3">
                    <p className="mb-1 text-xs font-semibold text-slate-500">Sources</p>
                    <ul className="space-y-1">
                      {answer.cited_sources.map((s, i) => (
                        <li key={`${s.source_url}-${i}`} className="text-xs">
                          <a className="text-accent-700 underline" href={s.source_url} target="_blank" rel="noopener noreferrer">
                            {s.title || s.source_url}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}

            {/* Verdict (AIQ-856) — captured for every answer/refusal that carries a trace_id */}
            {answer.trace_id && (
              <div className="flex items-center gap-3 border-t border-gray-100 pt-3" data-testid="immigration-answer-verdict">
                {verdict ? (
                  <span className="text-xs text-slate-500">Thanks — feedback recorded.</span>
                ) : (
                  <>
                    <span className="text-xs text-slate-500">Was this helpful?</span>
                    <Button variant="ghost" aria-label="Helpful" onClick={() => void rate('approved')}>👍</Button>
                    <Button variant="ghost" aria-label="Not helpful" onClick={() => void rate('rejected')}>👎</Button>
                    {verdictError && <span className="text-xs text-red-500">Couldn&apos;t save — try again.</span>}
                  </>
                )}
              </div>
            )}
          </div>
        </Card>
      )}

      {policyAnswer && policyStatus && (
        <Card>
          <div className="space-y-3 p-1" data-testid="policy-answer">
            <div className="flex items-center gap-2">
              <Badge variant="neutral">Your company policy</Badge>
              <span className={`rounded-full px-2 py-0.5 text-xs ${supportStatusBadgeClass(policyStatus)}`}>
                {supportStatusLabel(policyStatus)}
              </span>
            </div>
            <div className="whitespace-pre-wrap text-sm text-slate-800">
              {policyAnswer.answer_type === 'refusal'
                ? policyAnswer.refusal?.refusal_text
                : policyAnswer.answer_text}
            </div>
            {policyAnswer.cited_chunks && policyAnswer.cited_chunks.length > 0 && (
              <div className="border-t border-gray-100 pt-3">
                <p className="mb-1 text-xs font-semibold text-slate-500">Policy references</p>
                <ul className="space-y-1">
                  {policyAnswer.cited_chunks.map((c, i) => (
                    <li key={`${c.id}-${i}`} className="text-xs text-slate-600">{c.source_ref}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
