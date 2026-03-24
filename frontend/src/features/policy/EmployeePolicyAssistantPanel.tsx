/**
 * Bounded policy Q&A for employees: single-turn answers from published policy data (no chat UI).
 */
import React, { useCallback, useState } from 'react';
import { Alert, Button, Card } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import { formatRichMessage } from '../../utils/richMessage';
import type { PolicyAssistantAnswer } from '../../types/policyAssistant';
import {
  deriveSupportStatus,
  supportStatusBadgeClass,
  supportStatusLabel,
} from './employeePolicyAssistantModel';
import { trackPolicyAssistantFollowUpClicked } from './policyAssistantAnalytics';
import {
  EMPLOYEE_POLICY_ASSISTANT_NO_ASSIGNMENT,
  EMPLOYEE_POLICY_ASSISTANT_PLACEHOLDER,
  EMPLOYEE_POLICY_ASSISTANT_SCOPE_NOTE,
  EMPLOYEE_POLICY_ASSISTANT_SUBMIT,
  EMPLOYEE_POLICY_ASSISTANT_SUBTITLE,
  EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS,
  EMPLOYEE_POLICY_ASSISTANT_TITLE,
} from './employeePolicyAssistantCopy';

const MAX_TURNS = 5;

export type PolicyAssistantTurn = {
  id: string;
  question: string;
  answer: PolicyAssistantAnswer;
};

function newTurnId(): string {
  return `pa-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function AnswerResultCard({
  question,
  answer,
  onFollowUpSelect,
}: {
  question: string;
  answer: PolicyAssistantAnswer;
  onFollowUpSelect: (text: string, index: number, intent: string | undefined, canonicalTopic: string | null) => void;
}) {
  const status = deriveSupportStatus(answer);
  const isRefusal = status === 'refused';
  const isClarification = status === 'clarification';
  const primaryText =
    answer.answer_text?.trim() ||
    (isClarification && answer.refusal ? answer.refusal.refusal_text : '') ||
    (isRefusal && answer.refusal ? answer.refusal.refusal_text : '');

  return (
    <div
      className="rounded-lg border border-slate-200 bg-white shadow-sm"
      role="region"
      aria-label="Policy assistant result"
    >
      <div className="border-b border-slate-100 px-4 py-2.5 bg-slate-50/80">
        <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">Your question</div>
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
                <div className="text-xs font-semibold text-slate-600 mb-1.5">Try asking</div>
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
                  <p className="text-sm text-amber-950 mt-1">This benefit may require approval per policy.</p>
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
                <div className="text-xs font-semibold text-slate-600 mb-1.5">Related questions</div>
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
                            answer.canonical_topic ?? null
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

export const EmployeePolicyAssistantPanel: React.FC<{
  assignmentId: string | null | undefined;
  /** When true, hide “no assignment” until parent finished loading. */
  assignmentLoading?: boolean;
}> = ({ assignmentId, assignmentLoading = false }) => {
  const [message, setMessage] = useState('');
  const [turns, setTurns] = useState<PolicyAssistantTurn[]>([]);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const trimmed = message.trim();
  const canSubmit = Boolean(assignmentId && trimmed && !submitting);

  const submit = useCallback(async () => {
    if (!assignmentId || !trimmed) return;
    setSubmitting(true);
    setError('');
    try {
      const res = await employeeAPI.postPolicyAssistantQuery(assignmentId, trimmed);
      const answer = res.answer;
      setTurns((prev) => {
        const next = [...prev, { id: newTurnId(), question: trimmed, answer }];
        return next.length > MAX_TURNS ? next.slice(-MAX_TURNS) : next;
      });
      setMessage('');
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } }; message?: string };
      const d = ax.response?.data?.detail;
      setError(typeof d === 'string' ? d : ax.message || 'Could not get an answer. Try again.');
    } finally {
      setSubmitting(false);
    }
  }, [assignmentId, trimmed]);

  const applySuggestion = (q: string) => {
    setMessage(q);
    setError('');
  };

  const handleFollowUpFromAnswer = (
    text: string,
    index: number,
    intent: string | undefined,
    canonicalTopic: string | null
  ) => {
    trackPolicyAssistantFollowUpClicked({
      follow_up_intent: intent ?? undefined,
      follow_up_index: index,
      canonical_topic: canonicalTopic,
    });
    setMessage(text);
    setError('');
  };

  if (assignmentLoading && !assignmentId) {
    return (
      <Card padding="md" className="mb-6 border-slate-200 bg-slate-50/40">
        <div className="text-base font-semibold text-[#0b2b43]">{EMPLOYEE_POLICY_ASSISTANT_TITLE}</div>
        <p className="text-sm text-slate-500 mt-2">Loading your assignment…</p>
      </Card>
    );
  }

  if (!assignmentId) {
    return (
      <Card padding="md" className="mb-6 border-slate-200 bg-slate-50/50">
        <div className="text-base font-semibold text-[#0b2b43]">{EMPLOYEE_POLICY_ASSISTANT_TITLE}</div>
        <p className="text-sm text-slate-600 mt-1">{EMPLOYEE_POLICY_ASSISTANT_SUBTITLE}</p>
        <p className="text-sm text-slate-500 mt-3">{EMPLOYEE_POLICY_ASSISTANT_NO_ASSIGNMENT}</p>
      </Card>
    );
  }

  return (
    <Card padding="md" className="mb-6 border-slate-200">
      <div className="mb-1">
        <h2 className="text-base font-semibold text-[#0b2b43]">{EMPLOYEE_POLICY_ASSISTANT_TITLE}</h2>
        <p className="text-sm text-slate-600 mt-0.5">{EMPLOYEE_POLICY_ASSISTANT_SUBTITLE}</p>
      </div>
      <p className="text-xs text-slate-500 mt-2 leading-relaxed">{EMPLOYEE_POLICY_ASSISTANT_SCOPE_NOTE}</p>

      <div className="mt-4 space-y-2">
        <label htmlFor="policy-assistant-question" className="sr-only">
          Policy question
        </label>
        <textarea
          id="policy-assistant-question"
          rows={3}
          maxLength={8000}
          placeholder={EMPLOYEE_POLICY_ASSISTANT_PLACEHOLDER}
          className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 focus:border-slate-300"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={submitting}
          aria-describedby="policy-assistant-suggestions-hint"
        />
        <div id="policy-assistant-suggestions-hint" className="text-xs text-slate-500">
          Suggested questions (tap to fill the box, then get answer):
        </div>
        <div className="flex flex-wrap gap-2">
          {EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => applySuggestion(s)}
              disabled={submitting}
              className="text-left text-xs rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-slate-700 hover:bg-slate-100 disabled:opacity-50"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 pt-1">
          <Button type="button" onClick={() => void submit()} disabled={!canSubmit}>
            {submitting ? 'Working…' : EMPLOYEE_POLICY_ASSISTANT_SUBMIT}
          </Button>
        </div>
      </div>

      {error ? (
        <Alert variant="error" className="mt-3">
          {error}
        </Alert>
      ) : null}

      {turns.length > 0 ? (
        <div className="mt-5 space-y-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Results</div>
          {[...turns].reverse().map((t) => (
            <AnswerResultCard
              key={t.id}
              question={t.question}
              answer={t.answer}
              onFollowUpSelect={handleFollowUpFromAnswer}
            />
          ))}
        </div>
      ) : null}
    </Card>
  );
};
