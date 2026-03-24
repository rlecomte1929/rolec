/**
 * Bounded policy Q&A for HR: working draft, published signals, employee view — not a generic copilot.
 */
import React, { useCallback, useState } from 'react';
import { Alert, Button, Card } from '../../components/antigravity';
import { PolicyAssistantSideSheet } from './PolicyAssistantSideSheet';
import { hrAPI } from '../../api/client';
import { formatRichMessage } from '../../utils/richMessage';
import type { PolicyAssistantAnswer } from '../../types/policyAssistant';
import {
  deriveSupportStatus,
  supportStatusBadgeClass,
  supportStatusLabel,
} from './employeePolicyAssistantModel';
import {
  comparisonReadinessExplanation,
  draftVsPublishedHint,
  policyScopeLine,
} from './hrPolicyAssistantModel';
import { trackPolicyAssistantFollowUpClicked } from './policyAssistantAnalytics';
import {
  HR_POLICY_ASSISTANT_NO_POLICY,
  HR_POLICY_ASSISTANT_PLACEHOLDER,
  HR_POLICY_ASSISTANT_SCOPE_NOTE,
  HR_POLICY_ASSISTANT_SUBMIT,
  HR_POLICY_ASSISTANT_SUBTITLE,
  HR_POLICY_ASSISTANT_SUGGESTIONS,
  HR_POLICY_ASSISTANT_TITLE,
} from './hrPolicyAssistantCopy';

const MAX_TURNS = 5;

type Turn = { id: string; question: string; answer: PolicyAssistantAnswer; assistantRequestId?: string | null };

function newTurnId(): string {
  return `hr-pa-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function HrAnswerResultCard({
  question,
  answer,
  assistantTurnRequestId,
  onFollowUpSelect,
}: {
  question: string;
  answer: PolicyAssistantAnswer;
  assistantTurnRequestId?: string | null;
  onFollowUpSelect: (
    text: string,
    index: number,
    intent: string | undefined,
    canonicalTopic: string | null,
    turnRequestId: string | null | undefined
  ) => void;
}) {
  const status = deriveSupportStatus(answer);
  const isRefusal = status === 'refused';
  const isClarification = status === 'clarification';
  const primaryText =
    answer.answer_text?.trim() ||
    (isClarification && answer.refusal ? answer.refusal.refusal_text : '') ||
    (isRefusal && answer.refusal ? answer.refusal.refusal_text : '');

  const readinessLine = comparisonReadinessExplanation(answer.comparison_readiness);
  const dvpHint = draftVsPublishedHint(answer);

  return (
    <div
      className="rounded-lg border border-slate-200 bg-white shadow-sm"
      role="region"
      aria-label="HR policy answer"
    >
      <div className="border-b border-slate-100 px-4 py-2.5 bg-slate-50/80">
        <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">Question</div>
        <p className="text-sm text-slate-800 mt-0.5">{question}</p>
      </div>
      <div className="px-4 py-3 space-y-3">
        {isRefusal && answer.refusal ? (
          <>
            <div
              className={`inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-semibold ${supportStatusBadgeClass('refused')}`}
            >
              {supportStatusLabel('refused')}
            </div>
            <div className="text-sm text-slate-800 leading-relaxed">
              {formatRichMessage(answer.refusal.refusal_text)}
            </div>
            {answer.refusal.supported_examples.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-slate-600 mb-1.5">Within-policy examples</div>
                <ul className="text-sm text-slate-700 list-disc pl-5 space-y-1">
                  {answer.refusal.supported_examples.map((ex, i) => (
                    <li key={i}>{ex}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="rounded-md border border-slate-100 bg-slate-50/60 px-3 py-2 space-y-1.5 text-xs text-slate-700">
              <div>
                <span className="font-semibold text-slate-600">Policy data scope: </span>
                <span className="leading-relaxed">{formatRichMessage(policyScopeLine(answer.policy_status))}</span>
              </div>
              {dvpHint ? (
                <div>
                  <span className="font-semibold text-slate-600">Draft vs published: </span>
                  <span className="leading-relaxed">{formatRichMessage(dvpHint)}</span>
                </div>
              ) : null}
              {readinessLine ? (
                <div>
                  <span className="font-semibold text-slate-600">Comparison readiness: </span>
                  <span className="leading-relaxed">{formatRichMessage(readinessLine)}</span>
                </div>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-semibold ${supportStatusBadgeClass(status)}`}
              >
                {supportStatusLabel(status)}
              </span>
              {answer.canonical_topic ? (
                <span className="text-xs text-slate-500">
                  Topic: {answer.canonical_topic.replace(/_/g, ' ')}
                </span>
              ) : null}
            </div>

            {primaryText ? (
              <div className="text-sm text-slate-800 leading-relaxed">{formatRichMessage(primaryText)}</div>
            ) : null}

            {answer.evidence && answer.evidence.length > 0 ? (
              <div>
                <div className="text-xs font-semibold text-slate-600 mb-1">Source reference</div>
                <ul className="text-sm text-slate-700 space-y-2">
                  {answer.evidence.map((ev, i) => (
                    <li key={i} className="border-l-2 border-slate-200 pl-3">
                      <div className="font-medium text-slate-800">{ev.label || ev.kind}</div>
                      {ev.excerpt ? (
                        <div className="text-slate-600 mt-0.5 whitespace-pre-wrap text-xs leading-relaxed">
                          {ev.excerpt}
                        </div>
                      ) : null}
                      <div className="text-xs text-slate-500 mt-1">
                        {[ev.source, ev.section_ref, ev.policy_source_type].filter(Boolean).join(' · ')}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {(answer.approval_required || (answer.conditions && answer.conditions.length > 0)) && (
              <div className="rounded-md bg-amber-50/90 border border-amber-200 px-3 py-2">
                <div className="text-xs font-semibold text-amber-950">Approval & conditions</div>
                {answer.approval_required ? (
                  <p className="text-sm text-amber-950 mt-1">Published policy may require approval.</p>
                ) : null}
                {answer.conditions?.map((c, i) => (
                  <p key={i} className="text-sm text-amber-950 mt-1">
                    {c.text}
                  </p>
                ))}
              </div>
            )}

            {answer.follow_up_options && answer.follow_up_options.length > 0 ? (
              <div>
                <div className="text-xs font-semibold text-slate-600 mb-1.5">Related policy questions</div>
                <ul className="flex flex-wrap gap-2">
                  {answer.follow_up_options.map((opt, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        className="text-xs rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-slate-700 text-left hover:bg-slate-100"
                        onClick={() =>
                          onFollowUpSelect(
                            (opt.query_hint || opt.label).trim(),
                            i,
                            opt.intent,
                            answer.canonical_topic ?? null,
                            assistantTurnRequestId
                          )
                        }
                      >
                        {opt.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

export const HrPolicyAssistantPanel: React.FC<{
  policyId: string | null | undefined;
  documentId?: string | null;
  /** True while normalized policy payload for the selected policy is loading. */
  contextLoading?: boolean;
  /**
   * `card` — full-width block in page flow (tests, legacy).
   * `sideSheet` — top-right trigger; right panel on large screens, full-width sheet on small screens.
   */
  variant?: 'card' | 'sideSheet';
}> = ({ policyId, documentId, contextLoading = false, variant = 'card' }) => {
  const [message, setMessage] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const layoutSheet = variant === 'sideSheet';

  const pid = policyId?.trim() || null;
  const trimmed = message.trim();
  const canSubmit = Boolean(pid && trimmed && !submitting);

  const submit = useCallback(async () => {
    if (!pid || !trimmed) return;
    setSubmitting(true);
    setError('');
    try {
      const res = await hrAPI.postPolicyAssistantQuery(pid, trimmed, documentId?.trim() || undefined);
      setTurns((prev) => {
        const next = [
          ...prev,
          {
            id: newTurnId(),
            question: trimmed,
            answer: res.answer,
            assistantRequestId: res.request_id ?? null,
          },
        ];
        return next.length > MAX_TURNS ? next.slice(-MAX_TURNS) : next;
      });
      setMessage('');
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string | { message?: string } } }; message?: string };
      const d = ax.response?.data?.detail;
      const msg =
        typeof d === 'string'
          ? d
          : d && typeof d === 'object' && 'message' in d
            ? String((d as { message?: string }).message)
            : ax.message || 'Could not load a policy answer. Try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }, [pid, trimmed, documentId]);

  const applySuggestion = (q: string) => {
    setMessage(q);
    setError('');
  };

  const handleFollowUpFromAnswer = (
    text: string,
    index: number,
    intent: string | undefined,
    canonicalTopic: string | null,
    turnRequestId: string | null | undefined
  ) => {
    trackPolicyAssistantFollowUpClicked({
      follow_up_intent: intent ?? undefined,
      follow_up_index: index,
      canonical_topic: canonicalTopic,
      assistant_turn_request_id: turnRequestId ?? undefined,
    });
    setMessage(text);
    setError('');
  };

  if (contextLoading && !pid) {
    if (layoutSheet) return null;
    return (
      <Card padding="md" className="border-slate-200 bg-slate-50/40" id="hr-policy-assistant">
        <div className="text-base font-semibold text-[#0b2b43]">{HR_POLICY_ASSISTANT_TITLE}</div>
        <p className="text-sm text-slate-500 mt-2">Loading policy…</p>
      </Card>
    );
  }

  if (!pid) {
    if (layoutSheet) return null;
    return (
      <Card padding="md" className="border-slate-200 bg-slate-50/50" id="hr-policy-assistant">
        <div className="text-base font-semibold text-[#0b2b43]">{HR_POLICY_ASSISTANT_TITLE}</div>
        <p className="text-sm text-slate-600 mt-1">{HR_POLICY_ASSISTANT_SUBTITLE}</p>
        <p className="text-sm text-slate-500 mt-3">{HR_POLICY_ASSISTANT_NO_POLICY}</p>
      </Card>
    );
  }

  const questionId = layoutSheet ? 'hr-policy-assistant-question-sheet' : 'hr-policy-assistant-question';

  const coreForm = (
    <>
      <p
        className={`text-xs text-slate-500 leading-relaxed ${layoutSheet ? 'mt-0' : 'mt-2'}`}
      >
        {HR_POLICY_ASSISTANT_SCOPE_NOTE}
      </p>

      <div className="mt-4 space-y-2">
        <label htmlFor={questionId} className="sr-only">
          Policy question
        </label>
        <textarea
          id={questionId}
          rows={layoutSheet ? 5 : 3}
          maxLength={8000}
          placeholder={HR_POLICY_ASSISTANT_PLACEHOLDER}
          className={`w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 focus:border-slate-300 disabled:opacity-60${layoutSheet ? ' min-h-[5rem]' : ''}`}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={submitting || contextLoading}
          aria-describedby="hr-policy-assistant-suggestions-hint"
        />
        <div id="hr-policy-assistant-suggestions-hint" className="text-xs text-slate-500">
          Use a sample below or type a policy question, then submit.
        </div>
        <div className="flex flex-wrap gap-2">
          {HR_POLICY_ASSISTANT_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => applySuggestion(s)}
              disabled={submitting || contextLoading}
              className="text-left text-xs rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-slate-700 hover:bg-slate-100 disabled:opacity-50 max-w-full"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 pt-1">
          <Button type="button" onClick={() => void submit()} disabled={!canSubmit || contextLoading}>
            {submitting ? 'Checking policy…' : HR_POLICY_ASSISTANT_SUBMIT}
          </Button>
          {contextLoading ? <span className="text-xs text-slate-500">Workspace still loading…</span> : null}
        </div>
      </div>

      {error ? (
        <Alert variant="error" className="mt-3">
          {error}
        </Alert>
      ) : null}

      {turns.length > 0 ? (
        <div className="mt-5 space-y-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Policy answers</div>
          {[...turns].reverse().map((t) => (
            <HrAnswerResultCard
              key={t.id}
              question={t.question}
              answer={t.answer}
              assistantTurnRequestId={t.assistantRequestId}
              onFollowUpSelect={handleFollowUpFromAnswer}
            />
          ))}
        </div>
      ) : null}
    </>
  );

  if (layoutSheet) {
    return (
      <PolicyAssistantSideSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        title={HR_POLICY_ASSISTANT_TITLE}
        subtitle={HR_POLICY_ASSISTANT_SUBTITLE}
        titleId="hr-policy-assistant-sheet-title"
        trigger={
          <div className="sticky top-0 z-10 -mx-1 mb-4 flex flex-col items-end gap-1 bg-gradient-to-b from-white from-80% to-transparent pb-1 pt-1 px-1 sm:-mx-0">
            <Button
              type="button"
              variant="outline"
              className="shrink-0 border-slate-300 text-[#0b2b43] font-medium shadow-sm"
              onClick={() => setSheetOpen(true)}
            >
              {HR_POLICY_ASSISTANT_TITLE}
            </Button>
            <p className="hidden max-w-[15rem] text-right text-xs leading-snug text-slate-500 md:block">
              Opens as a side panel. Workspace stays open.
            </p>
          </div>
        }
      >
        {coreForm}
      </PolicyAssistantSideSheet>
    );
  }

  return (
    <Card padding="md" className="border-slate-200" id="hr-policy-assistant">
      <div className="mb-1">
        <h2 className="text-base font-semibold text-[#0b2b43]">{HR_POLICY_ASSISTANT_TITLE}</h2>
        <p className="text-sm text-slate-600 mt-0.5">{HR_POLICY_ASSISTANT_SUBTITLE}</p>
      </div>
      {coreForm}
    </Card>
  );
};
