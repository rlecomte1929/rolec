import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/antigravity/Button';
import { createAIDecision } from '../../api/aiDecisions';
import type { AIDecisionAction, AIDecisionRecord } from '../../api/aiDecisions';

/**
 * AIRecommendationCard (AI-002) — EU AI Act Art. 14 human oversight surface.
 *
 * Every AI-generated recommendation shown to an HR admin renders through this
 * card. The card displays the rationale and forces an explicit accept / override /
 * reject from the HR admin before any downstream action treats the AI output as
 * acted-on. Override and reject require a reason. Every action is logged to
 * `public.ai_decisions` via POST /api/ai/decisions.
 */

export interface AIRecommendationCardProps {
  /**
   * Stable identifier for the specific AI recommendation (e.g. the row id of
   * the underlying entity, or a deterministic hash of the recommendation).
   * Used to dedupe and to correlate the decision with the AI output later.
   */
  recommendationId: string;

  /**
   * AI feature key — used for filtering in the audit view.
   * Examples: 'exception_insight', 'assignment_match', 'case_readiness'.
   */
  feature: string;

  /** Short, human-readable label shown in the card header. */
  title?: string;

  /** Plain-text rationale shown to the HR admin. Required by Art. 14(4)(a). */
  rationale: React.ReactNode;

  /**
   * Full AI recommendation payload as shown to the HR admin. Stored in
   * `ai_decisions.ai_output` for audit replay.
   */
  aiOutput: Record<string, unknown>;

  /** Optional confidence score (0-1) to render as a badge. */
  confidence?: number;

  /** TASK-008: when both are provided, the card leads with the checkpoint
   * count ('N of X checkpoints satisfied') as the primary metric and demotes
   * confidence to a labelled secondary line. Used by the case-readiness card so
   * HR doesn't read a low confidence % as the platform being unreliable. */
  checkpointsSatisfied?: number;
  checkpointsTotal?: number;

  /** Called after a decision is successfully recorded. */
  onDecisionRecorded?: (record: AIDecisionRecord) => void;
}

const ACTION_CONFIG: Record<AIDecisionAction, { label: string; pill: string }> = {
  accept: {
    label: 'Accept recommendation',
    pill: 'bg-emerald-600 hover:bg-emerald-700 text-white',
  },
  override: {
    label: 'Override',
    pill: 'bg-amber-500 hover:bg-amber-600 text-white',
  },
  reject: {
    label: 'Reject',
    pill: 'bg-rose-600 hover:bg-rose-700 text-white',
  },
};

const REASON_REQUIRED: AIDecisionAction[] = ['override', 'reject'];

export const AIRecommendationCard: React.FC<AIRecommendationCardProps> = ({
  recommendationId,
  feature,
  title = 'AI recommendation',
  rationale,
  aiOutput,
  confidence,
  checkpointsSatisfied,
  checkpointsTotal,
  onDecisionRecorded,
}) => {
  const [pendingAction, setPendingAction] = useState<AIDecisionAction | null>(null);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<AIDecisionRecord | null>(null);
  const [priorDecision, setPriorDecision] = useState<AIDecisionRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reasonRequired = pendingAction !== null && REASON_REQUIRED.includes(pendingAction);
  const reasonMissing = reasonRequired && !reason.trim();

  const reset = () => {
    setPendingAction(null);
    setReason('');
    setError(null);
  };

  const changeDecision = () => {
    if (!submitted) return;
    setPriorDecision(submitted);
    setSubmitted(null);
    setPendingAction(null);
    setReason('');
    setError(null);
  };

  const submit = async () => {
    if (!pendingAction || submitting) return;
    if (reasonMissing) {
      setError(`A reason is required to ${pendingAction} the recommendation.`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { ...aiOutput };
      if (priorDecision) {
        payload.prior_decision = {
          id: priorDecision.id,
          decision: priorDecision.decision,
          reason: priorDecision.reason,
          created_at: priorDecision.created_at,
        };
      }
      const record = await createAIDecision({
        feature,
        recommendation_id: recommendationId,
        ai_output: payload,
        decision: pendingAction,
        reason: reason.trim() || undefined,
      });
      setSubmitted(record);
      onDecisionRecorded?.(record);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to record decision';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    const action = submitted.decision;
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-start gap-3">
          <svg className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="flex-1 text-sm text-slate-700">
            <strong>AI recommendation {action === 'accept' ? 'accepted' : action === 'override' ? 'overridden' : 'rejected'}.</strong>
            {submitted.reason && (
              <p className="text-xs text-slate-500 italic mt-1">Reason: &quot;{submitted.reason}&quot;</p>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
              <p className="text-[11px] text-slate-500">Logged for human oversight audit · EU AI Act Art. 14</p>
              <Button unstyled
                type="button"
                onClick={changeDecision}
                className="text-[11px] font-medium text-accent-600 hover:text-accent-800 underline-offset-2 hover:underline"
              >
                Change decision
              </Button>
              <Link
                to={`/hr/ai-decisions?recommendation_id=${encodeURIComponent(recommendationId)}`}
                className="text-[11px] font-medium text-accent-600 hover:text-accent-800 underline-offset-2 hover:underline"
              >
                View in audit
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-accent-200 bg-accent-50 px-4 py-3">
      <div className="flex gap-3">
        <svg className="w-4 h-4 text-accent-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <div className="flex-1 min-w-0">
          {typeof checkpointsTotal === 'number' && typeof checkpointsSatisfied === 'number' ? (
            // TASK-008: lead with the actionable checkpoint count; confidence is
            // a labelled secondary so a low % reads as incomplete data, not an
            // unreliable platform. (Sentence-case header for this variant.)
            <>
              <div className="text-xs font-semibold text-accent-700 mb-1">{title}</div>
              <div className="text-2xl font-semibold text-accent-800 leading-tight">
                {checkpointsSatisfied} of {checkpointsTotal} checkpoints satisfied
              </div>
              {typeof confidence === 'number' && (
                <div className="flex items-center gap-1 text-xs text-accent-600 mt-1">
                  <span>Confidence score: {Math.round(confidence * 100)}%</span>
                  <span
                    className="cursor-help select-none border border-accent-300 rounded-full w-3.5 h-3.5 inline-flex items-center justify-center text-[9px] leading-none"
                    title="Confidence increases as intake fields and documents are completed. At 100%, all required information is available for AI-assisted decisions."
                    aria-label="Confidence increases as intake fields and documents are completed. At 100%, all required information is available for AI-assisted decisions."
                  >
                    i
                  </span>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-xs font-semibold text-accent-700 uppercase tracking-wider">{title}</span>
              {typeof confidence === 'number' && (
                <span className="text-[10px] text-accent-600">{Math.round(confidence * 100)}% confidence</span>
              )}
            </div>
          )}
          <div className="text-sm text-accent-800 leading-relaxed mt-1">{rationale}</div>
          <p className="text-[11px] text-accent-600 mt-1">AI-generated · Your decision is required and logged for your EU AI Act audit trail.</p>

          {priorDecision && (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <strong>Changing previous decision.</strong>
              <span className="ml-1">
                You previously {priorDecision.decision === 'accept' ? 'accepted' : priorDecision.decision === 'override' ? 'overrode' : 'rejected'} this recommendation
                {priorDecision.reason ? <> with reason <span className="italic">&quot;{priorDecision.reason}&quot;</span></> : null}.
              </span>
              <p className="text-[11px] text-amber-700 mt-1">The previous decision stays in the audit log; the new decision is recorded as a separate row referencing it.</p>
            </div>
          )}

          <div className="mt-3 flex flex-wrap gap-2">
            {(Object.keys(ACTION_CONFIG) as AIDecisionAction[]).map((action) => (
              <Button unstyled
                key={action}
                type="button"
                onClick={() => setPendingAction(action)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  pendingAction === action
                    ? ACTION_CONFIG[action].pill
                    : 'bg-white text-accent-700 border border-accent-200 hover:bg-accent-100'
                }`}
              >
                {ACTION_CONFIG[action].label}
              </Button>
            ))}
          </div>

          {pendingAction && (
            <div className="mt-3 space-y-2">
              <label className="block">
                <span className="text-xs font-medium text-slate-600">
                  Reason
                  {reasonRequired
                    ? <span className="text-rose-500 ml-1">*</span>
                    : <span className="text-slate-500 ml-1">(optional)</span>}
                </span>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={2}
                  placeholder={
                    pendingAction === 'accept'
                      ? 'Optional context for the audit trail.'
                      : 'Explain why the AI recommendation does not fit this case.'
                  }
                  className="mt-1 w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-accent-200 resize-none bg-white"
                />
              </label>
              {error && <p className="text-xs text-rose-600">{error}</p>}
              <div className="flex items-center gap-2">
                <Button unstyled
                  type="button"
                  onClick={reset}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800 transition-colors"
                  disabled={submitting}
                >
                  Cancel
                </Button>
                <Button unstyled
                  type="button"
                  onClick={submit}
                  disabled={submitting || reasonMissing}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors text-white disabled:opacity-40 disabled:cursor-not-allowed ${ACTION_CONFIG[pendingAction].pill}`}
                >
                  {submitting ? 'Recording…' : `Confirm ${pendingAction}`}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
