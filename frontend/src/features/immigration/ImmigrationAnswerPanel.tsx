import { useState } from 'react';
import { CountryPicker } from '../../components/location';
import { Alert, Badge, Button, Card, Input } from '../../components/antigravity';
import { CountryMultiSelect } from '../policy-config/CountryMultiSelect';
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

// Guided starters — lower the blank-page barrier on the free-text Q&A (mirrors the
// policy assistant's question tiles). Clicking one fills the question box.
const SUGGESTED_QUESTIONS = [
  'What documents do I need for the visa application?',
  'How long does the visa process usually take?',
  'Can my spouse work on a dependent visa?',
  'What are the salary or qualification requirements?',
];

type ConfidenceBadge = { label: string; variant: 'success' | 'info' | 'warning' | 'neutral' };

function confidenceBadge(confidence?: string | null): ConfidenceBadge {
  switch ((confidence || '').toLowerCase()) {
    case 'high': return { label: 'High confidence', variant: 'success' };
    case 'medium': return { label: 'Medium confidence', variant: 'info' };
    case 'low': return { label: 'Low confidence', variant: 'warning' };
    default: return { label: 'Confidence: unknown', variant: 'neutral' };
  }
}

/**
 * Corridor derived from the employee's own case (relocation-assistant MVP). When
 * present the panel pre-fills the corridor instead of making the employee hand-type
 * From/To — "answering for YOUR move" — with an Edit affordance to override.
 */
export interface ImmigrationCaseContext {
  from: string;
  to: string;
  nationality?: string;
  /** AIQ-1476: one or more nationalities pre-filled from the intake form (dual nationals). */
  nationalities?: string[];
  permitType?: string;
  /** Human label, e.g. "IN → DE". Falls back to `from → to`. */
  label?: string;
}

export function ImmigrationAnswerPanel(
  { caseId, caseContext }: { caseId?: string | null; caseContext?: ImmigrationCaseContext } = {},
) {
  const [from, setFrom] = useState(caseContext?.from ?? '');
  const [to, setTo] = useState(caseContext?.to ?? '');
  // AIQ-1476: nationality is multi-value (dual nationals) and pre-filled from intake.
  const [nationalities, setNationalities] = useState<string[]>(
    caseContext?.nationalities?.length
      ? caseContext.nationalities
      : caseContext?.nationality
        ? [caseContext.nationality]
        : [],
  );
  const [permitType, setPermitType] = useState(caseContext?.permitType ?? '');
  // AIQ-1476: permit type is optional context, not a prerequisite — the assistant's job
  // is to help determine it. Hidden behind "Advanced" so it never blocks a question.
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [query, setQuery] = useState('');
  // Show the manual corridor form when there's no case context, or the employee
  // chose to override the auto-detected corridor.
  const [editingCorridor, setEditingCorridor] = useState(!caseContext);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<ImmigrationAnswer | null>(null);
  const [policyAnswer, setPolicyAnswer] = useState<PolicyAssistantAnswer | null>(null);
  const [clarifyFor, setClarifyFor] = useState<string | null>(null);

  const [verdict, setVerdict] = useState<FeedbackVerdict | null>(null);
  const [verdictError, setVerdictError] = useState(false);

  const canAsk = !!query.trim();
  // AIQ-1476: permit type dropped from the gate (the assistant determines it). Nationality
  // is now pre-filled from intake, so this is satisfied automatically for most employees.
  const corridorComplete = !!(from.trim() && to.trim() && nationalities.length > 0);

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
        setError('Add your move corridor (From / To) and at least one nationality above for immigration questions.');
        return;
      }
      setLoading(true);
      try {
        const res = await askImmigrationQuestion({
          corridor_from: from.trim().toUpperCase(),
          corridor_to: to.trim().toUpperCase(),
          // The immigration engine keys on a single nationality; send the primary one.
          // Dual nationals can reorder to pick which applies to this corridor.
          nationality: (nationalities[0] ?? '').trim().toUpperCase(),
          permit_type: permitType.trim(),
          query: q,
          ...(caseId ? { case_id: caseId } : {}),
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

  // AIQ-1476: nationality (pre-filled from intake, editable, multi-value) + an optional
  // "Advanced" permit-type field — permit is never a prerequisite for asking.
  const corridorFields = (
    <>
      <div>
        <span className="text-xs font-medium text-slate-500">Your nationality(ies)</span>
        <div className="mt-1">
          <CountryMultiSelect value={nationalities} onChange={setNationalities} />
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Pre-filled from your intake — add more if you hold multiple nationalities.
        </p>
      </div>
      <div>
        <Button
          unstyled
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="text-xs text-slate-500 underline hover:text-slate-700"
        >
          {showAdvanced ? 'Hide advanced' : 'Advanced (permit type)'}
        </Button>
        {showAdvanced ? (
          <div className="mt-2">
            <Input
              aria-label="Permit type"
              placeholder="Permit type (optional)"
              value={permitType}
              onChange={(v) => setPermitType(v)}
            />
          </div>
        ) : (
          <p className="mt-1 text-xs text-slate-500">
            Not sure of your permit type? That&apos;s fine — the assistant will help determine it.
          </p>
        )}
      </div>
    </>
  );

  return (
    <div className="w-full space-y-4">
      <Card>
        <div className="space-y-3 p-1">
          <p className="text-sm text-slate-600">
            Ask about <strong>your move</strong> (visas, permits, documents) or <strong>your company&apos;s
            benefits</strong> (allowances, what&apos;s covered). Both answers are grounded and cite where each
            point comes from.
          </p>
          {caseContext && !editingCorridor ? (
            <div className="space-y-3">
              {/* AIQ-1476: corridor comes from your case and is shown prominently — the
                  employee no longer has to hand-type From/To/Nationality. */}
              <div className="flex items-center justify-between gap-3 rounded-lg border border-accent-100 bg-accent-50 px-3 py-2">
                <p className="text-sm text-slate-700">
                  Answering for{' '}
                  <span className="font-semibold text-navy-800">your {caseContext.label ?? `${from} → ${to}`} move</span>
                  {nationalities.length > 0 && (
                    <span className="text-slate-500"> · {nationalities.join(', ')}</span>
                  )}
                </p>
                <Button variant="ghost" onClick={() => setEditingCorridor(true)} aria-label="Use a different corridor">
                  Edit corridor
                </Button>
              </div>
              {corridorFields}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                {/* Labels kept verbatim ("From country"/"To country"): they are the
                    accessible names the existing tests and screen readers already rely on.
                    Changing a control's type should not rename it. */}
                <CountryPicker label="From country" value={from} onChange={setFrom} testId="imm-answer-from" />
                <CountryPicker label="To country" value={to} onChange={setTo} testId="imm-answer-to" />
              </div>
              {corridorFields}
            </div>
          )}
          <textarea
            aria-label="Your question"
            className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-accent-500"
            rows={3}
            placeholder="e.g. What documents do I need? · Does my company cover temporary housing?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {!query.trim() && (
            <div className="flex flex-wrap gap-2" aria-label="Suggested questions">
              {SUGGESTED_QUESTIONS.map((q) => (
                <Button
                  key={q}
                  unstyled
                  type="button"
                  onClick={() => setQuery(q)}
                  className="rounded-full border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:border-[#0b2b43] hover:text-[#0b2b43]"
                >
                  {q}
                </Button>
              ))}
            </div>
          )}
          <div className="flex items-center gap-3">
            <Button variant="primary" onClick={() => void ask()} disabled={!canAsk || loading}>
              {loading ? 'Asking…' : 'Ask'}
            </Button>
            <span className="text-xs text-gray-500">Grounded + cited · always confirm with the cited source</span>
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
