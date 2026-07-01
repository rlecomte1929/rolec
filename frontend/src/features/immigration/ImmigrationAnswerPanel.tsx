import { useState } from 'react';
import { Alert, Badge, Button, Card, Input } from '../../components/antigravity';
import {
  askImmigrationQuestion,
  type ImmigrationAnswer,
} from '../../api/immigrationAnswer';
import { submitAiFeedback, type FeedbackVerdict } from '../../api/aiFeedback';

/**
 * Employee-facing grounded immigration Q&A (AIQ-843 backend + AIQ-856 verdict).
 * Asks /api/immigration/answer for a corridor + question, renders the cited
 * answer, and captures a 👍/👎 verdict into ai_human_feedback (reliability loop;
 * ships dormant — RELIABILITY_WEIGHT=0 — so feedback accrues before it affects ranking).
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

/**
 * Corridor derived from the employee's own case (relocation-assistant MVP). When
 * present the panel pre-fills the corridor instead of making the employee hand-type
 * From/To — "answering for YOUR move" — with an Edit affordance to override.
 */
export interface ImmigrationCaseContext {
  from: string;
  to: string;
  nationality?: string;
  permitType?: string;
  /** Human label, e.g. "IN → DE". Falls back to `from → to`. */
  label?: string;
}

export function ImmigrationAnswerPanel(
  { caseId, caseContext }: { caseId?: string | null; caseContext?: ImmigrationCaseContext } = {},
) {
  const [from, setFrom] = useState(caseContext?.from ?? '');
  const [to, setTo] = useState(caseContext?.to ?? '');
  const [nationality, setNationality] = useState(caseContext?.nationality ?? '');
  const [permitType, setPermitType] = useState(caseContext?.permitType ?? '');
  const [query, setQuery] = useState('');
  // Show the manual corridor form when there's no case context, or the employee
  // chose to override the auto-detected corridor.
  const [editingCorridor, setEditingCorridor] = useState(!caseContext);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<ImmigrationAnswer | null>(null);

  const [verdict, setVerdict] = useState<FeedbackVerdict | null>(null);
  const [verdictError, setVerdictError] = useState(false);

  const canAsk = !!(from.trim() && to.trim() && nationality.trim() && permitType.trim() && query.trim());

  async function ask() {
    if (!canAsk) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    setVerdict(null);
    setVerdictError(false);
    try {
      const res = await askImmigrationQuestion({
        corridor_from: from.trim().toUpperCase(),
        corridor_to: to.trim().toUpperCase(),
        nationality: nationality.trim().toUpperCase(),
        permit_type: permitType.trim(),
        query: query.trim(),
        ...(caseId ? { case_id: caseId } : {}),
      });
      setAnswer(res);
    } catch {
      setError('Could not get an answer right now. Please try again.');
    } finally {
      setLoading(false);
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

  return (
    <div className="max-w-3xl space-y-4">
      <Card>
        <div className="space-y-3 p-1">
          <p className="text-sm text-slate-600">
            Ask a grounded immigration question for your corridor. Answers are sourced
            only from official guidance and cite where each point comes from.
          </p>
          {caseContext && !editingCorridor ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3 rounded-lg border border-accent-100 bg-accent-50 px-3 py-2">
                <p className="text-sm text-slate-700">
                  Answering for{' '}
                  <span className="font-semibold text-navy-800">your {caseContext.label ?? `${from} → ${to}`} move</span>
                  {permitType && <span className="text-slate-500"> · {permitType}</span>}
                </p>
                <Button variant="ghost" onClick={() => setEditingCorridor(true)} aria-label="Use a different corridor">
                  Edit corridor
                </Button>
              </div>
              {/* Corridor comes from your case; confirm the details we don't yet hold. */}
              {(!caseContext.nationality || !caseContext.permitType) && (
                <div className="grid grid-cols-2 gap-3">
                  {!caseContext.nationality && (
                    <Input aria-label="Nationality" placeholder="Your nationality (e.g. IN)" value={nationality} onChange={(v) => setNationality(v)} />
                  )}
                  {!caseContext.permitType && (
                    <Input aria-label="Permit type" placeholder="Permit (e.g. work)" value={permitType} onChange={(v) => setPermitType(v)} />
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Input aria-label="From country" placeholder="From (e.g. IN)" value={from} onChange={(v) => setFrom(v)} />
              <Input aria-label="To country" placeholder="To (e.g. DE)" value={to} onChange={(v) => setTo(v)} />
              <Input aria-label="Nationality" placeholder="Nationality (e.g. IN)" value={nationality} onChange={(v) => setNationality(v)} />
              <Input aria-label="Permit type" placeholder="Permit (e.g. work)" value={permitType} onChange={(v) => setPermitType(v)} />
            </div>
          )}
          <textarea
            aria-label="Your question"
            className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800 placeholder-gray-300 focus:outline-none focus:ring-1 focus:ring-accent-500"
            rows={3}
            placeholder="e.g. What documents do I need for the work visa application?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="flex items-center gap-3">
            <Button variant="primary" onClick={() => void ask()} disabled={!canAsk || loading}>
              {loading ? 'Asking…' : 'Ask'}
            </Button>
            <span className="text-xs text-gray-400">Official sources only · always confirm with the cited authority</span>
          </div>
        </div>
      </Card>

      {error && <Alert variant="error">{error}</Alert>}

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
    </div>
  );
}
