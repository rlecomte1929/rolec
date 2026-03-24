/**
 * Bounded policy Q&A for employees: single-turn answers from published policy data.
 * HR Policy page: `sideSheet` — right anchored panel (desktop) / sheet (mobile), not a floating chat bubble.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Copy, Loader2 } from 'lucide-react';
import { Alert, Button, Card } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import { formatRichMessage } from '../../utils/richMessage';
import type { PolicyAssistantAnswer } from '../../types/policyAssistant';
import { formatEvidenceAttribution } from './policyEvidenceFormatting';
import {
  clearEmployeePolicyAssistantTurns,
  loadEmployeePolicyAssistantTurns,
  saveEmployeePolicyAssistantTurns,
} from './employeePolicyAssistantStorage';
import {
  deriveSupportStatus,
  supportStatusBadgeClass,
  supportStatusLabel,
} from './employeePolicyAssistantModel';
import { trackPolicyAssistantFollowUpClicked } from './policyAssistantAnalytics';
import {
  EMPLOYEE_POLICY_ASSISTANT_CLEAR_HISTORY,
  EMPLOYEE_POLICY_ASSISTANT_COPIED,
  EMPLOYEE_POLICY_ASSISTANT_COPY_ANSWER,
  EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER,
  EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER_SECONDARY,
  EMPLOYEE_POLICY_ASSISTANT_EMPTY_HINT,
  EMPLOYEE_POLICY_ASSISTANT_ERROR_DETAIL,
  EMPLOYEE_POLICY_ASSISTANT_ERROR_TITLE,
  EMPLOYEE_POLICY_ASSISTANT_NO_ASSIGNMENT,
  EMPLOYEE_POLICY_ASSISTANT_PLACEHOLDER,
  EMPLOYEE_POLICY_ASSISTANT_SAVED_HINT,
  EMPLOYEE_POLICY_ASSISTANT_SHORTCUTS_TITLE,
  EMPLOYEE_POLICY_ASSISTANT_SUBMIT,
  EMPLOYEE_POLICY_ASSISTANT_SUBTITLE,
  EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS,
  EMPLOYEE_POLICY_ASSISTANT_TITLE,
} from './employeePolicyAssistantCopy';
import { PolicyAssistantSideSheet } from './PolicyAssistantSideSheet';

const MAX_TURNS = 15;

function stripBoldMarkers(s: string): string {
  return s.replace(/\*\*([^*]+)\*\*/g, '$1');
}

function topicLabel(canonical: string | null | undefined): string {
  if (!canonical?.trim()) return '';
  return canonical.replace(/_/g, ' ');
}

function policyAssistantUserFacingError(raw: string): { title: string; detail?: string } {
  const t = raw.trim();
  if (!t || /^policy assistant failed$/i.test(t)) {
    return { title: EMPLOYEE_POLICY_ASSISTANT_ERROR_TITLE, detail: EMPLOYEE_POLICY_ASSISTANT_ERROR_DETAIL };
  }
  return { title: t };
}

function turnToPlainText(question: string, answer: PolicyAssistantAnswer): string {
  const status = deriveSupportStatus(answer);
  const lines = [
    `Question: ${question}`,
    '',
    `Status: ${supportStatusLabel(status)}`,
    '',
  ];
  const isRefusal = status === 'refused';
  const isClarification = status === 'clarification';
  const body =
    answer.answer_text?.trim() ||
    (isClarification && answer.refusal ? answer.refusal.refusal_text : '') ||
    (isRefusal && answer.refusal ? answer.refusal.refusal_text : '');
  if (body) lines.push(stripBoldMarkers(body), '');
  if (answer.evidence?.length) {
    lines.push('Sources:');
    for (const ev of answer.evidence) {
      lines.push(`- ${formatEvidenceAttribution(ev)}`);
      if (ev.excerpt?.trim()) lines.push(`  ${stripBoldMarkers(ev.excerpt.trim())}`);
    }
  }
  return lines.join('\n').trim();
}

export type PolicyAssistantTurn = {
  id: string;
  question: string;
  answer: PolicyAssistantAnswer;
  assistantRequestId?: string | null;
};

function newTurnId(): string {
  return `pa-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function humanizeEvidenceKind(kind: string | undefined): string {
  if (!kind?.trim()) return 'Policy source';
  return kind.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function AnswerResultCard({
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
  const [copied, setCopied] = useState(false);
  const status = deriveSupportStatus(answer);
  const isRefusal = status === 'refused';
  const isClarification = status === 'clarification';
  const primaryText =
    answer.answer_text?.trim() ||
    (isClarification && answer.refusal ? answer.refusal.refusal_text : '') ||
    (isRefusal && answer.refusal ? answer.refusal.refusal_text : '');

  const handleCopy = async () => {
    const text = turnToPlainText(question, answer);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const topic = topicLabel(answer.canonical_topic);

  return (
    <article
      className="overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-[0_2px_14px_rgba(15,23,42,0.06)] ring-1 ring-slate-100/80"
      role="article"
      aria-label="Policy Q&A"
    >
      <div className="border-b border-slate-200/90 bg-gradient-to-r from-slate-50 to-[#f4f7fb] px-4 py-3.5">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Your question</div>
        <p className="mt-1.5 text-[15px] font-medium leading-snug text-[#0b2b43]">{question}</p>
      </div>

      <div className="space-y-4 px-4 py-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {isRefusal && answer.refusal ? (
              <span
                className={`inline-flex items-center rounded-full border px-3 py-0.5 text-xs font-semibold ${supportStatusBadgeClass('refused')}`}
              >
                {supportStatusLabel('refused')}
              </span>
            ) : (
              <>
                <span
                  className={`inline-flex items-center rounded-full border px-3 py-0.5 text-xs font-semibold ${supportStatusBadgeClass(status)}`}
                >
                  {supportStatusLabel(status)}
                </span>
                {topic ? (
                  <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-0.5 text-xs font-medium capitalize text-slate-700">
                    {topic}
                  </span>
                ) : null}
              </>
            )}
          </div>
          <button
            type="button"
            onClick={() => void handleCopy()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50 hover:text-[#0b2b43]"
          >
            <Copy className="h-3.5 w-3.5 opacity-70" aria-hidden />
            {copied ? EMPLOYEE_POLICY_ASSISTANT_COPIED : EMPLOYEE_POLICY_ASSISTANT_COPY_ANSWER}
          </button>
        </div>

        {isRefusal && answer.refusal ? (
          <>
            <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-4 py-3.5 text-[15px] leading-[1.65] text-slate-800">
              {formatRichMessage(answer.refusal.refusal_text)}
            </div>
            {answer.refusal.supported_examples.length > 0 ? (
              <div className="rounded-lg border border-slate-100 bg-white px-3 py-3">
                <div className="text-xs font-semibold text-slate-600 mb-2">Policy questions you can ask</div>
                <ul className="text-sm text-slate-700 list-disc pl-5 space-y-1.5 leading-relaxed">
                  {answer.refusal.supported_examples.map((ex, i) => (
                    <li key={i}>{ex}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : (
          <>
            {primaryText ? (
              <div className="rounded-lg border border-[#e2e8f0] bg-[#fafbfd] px-4 py-3.5 text-[15px] leading-[1.65] text-slate-800">
                {formatRichMessage(primaryText)}
              </div>
            ) : null}

            {answer.evidence && answer.evidence.length > 0 ? (
              <details className="rounded-lg border border-slate-200/80 bg-white open:shadow-sm" open>
                <summary className="cursor-pointer list-none px-3 py-2.5 text-xs font-semibold text-slate-600 marker:content-none [&::-webkit-details-marker]:hidden">
                  Where this comes from
                </summary>
                <ul className="space-y-3 border-t border-slate-100 px-3 py-3">
                  {answer.evidence.map((ev, i) => {
                    const headline = (ev.label || humanizeEvidenceKind(ev.kind)).trim();
                    const attribution = formatEvidenceAttribution(ev).trim();
                    const showExtraAttribution = attribution.length > 0 && attribution !== headline;
                    return (
                      <li key={i} className="border-l-[3px] border-[#0b2b43]/25 pl-3">
                        <div className="text-sm font-semibold text-[#0b2b43]">{headline}</div>
                        {ev.excerpt ? (
                          <div className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-600">{ev.excerpt}</div>
                        ) : null}
                        {showExtraAttribution ? (
                          <div className="mt-1.5 text-xs leading-relaxed text-slate-500">{attribution}</div>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </details>
            ) : null}

            {(answer.approval_required || (answer.conditions && answer.conditions.length > 0)) && (
              <div className="rounded-lg bg-amber-50/90 border border-amber-200 px-3.5 py-3">
                <div className="text-xs font-semibold text-amber-950">Approval & conditions</div>
                {answer.approval_required ? (
                  <p className="text-sm text-amber-950 mt-1.5 leading-relaxed">
                    Published policy may require approval for this benefit.
                  </p>
                ) : null}
                {answer.conditions?.map((c, i) => (
                  <p key={i} className="text-sm text-amber-950 mt-1.5 leading-relaxed">
                    {c.text}
                  </p>
                ))}
              </div>
            )}

            {answer.follow_up_options && answer.follow_up_options.length > 0 ? (
              <div>
                <div className="text-xs font-semibold text-slate-600 mb-2">Related policy questions</div>
                <ul className="flex flex-wrap gap-2">
                  {answer.follow_up_options.map((opt, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm font-medium text-slate-700 shadow-sm transition-colors hover:border-[#0b2b43]/25 hover:bg-slate-50"
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
    </article>
  );
}

export const EmployeePolicyAssistantPanel: React.FC<{
  assignmentId: string | null | undefined;
  /** When true, hide “no assignment” until parent finished loading. */
  assignmentLoading?: boolean;
  /**
   * `card` — full-width panel (legacy in-page placement).
   * `sideSheet` — HR Policy: triggers beside/near content; panel from the right (desktop) or sheet (mobile).
   * @deprecated Use `sideSheet`. `fab` is treated as `sideSheet`.
   */
  variant?: 'card' | 'fab' | 'sideSheet';
}> = ({ assignmentId, assignmentLoading = false, variant = 'card' }) => {
  const layoutVariant = variant === 'fab' ? 'sideSheet' : variant;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const responseSectionRef = useRef<HTMLElement | null>(null);
  const scrollToResponseAfterAnswerRef = useRef(false);
  const [message, setMessage] = useState('');
  const [turns, setTurns] = useState<PolicyAssistantTurn[]>([]);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [emptySubmitHint, setEmptySubmitHint] = useState(false);

  useEffect(() => {
    if (!assignmentId) {
      setTurns([]);
      return;
    }
    setTurns(loadEmployeePolicyAssistantTurns(assignmentId));
  }, [assignmentId]);

  const focusQuestionInput = useCallback(() => {
    window.setTimeout(() => {
      textareaRef.current?.focus({ preventScroll: false });
    }, 0);
  }, []);

  useEffect(() => {
    if (!scrollToResponseAfterAnswerRef.current || submitting) return;
    scrollToResponseAfterAnswerRef.current = false;
    const el = responseSectionRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      if (typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  }, [turns, submitting]);

  const trimmed = message.trim();
  const inputEmpty = trimmed.length === 0;
  const buttonInactiveLook = Boolean(assignmentId && !submitting && inputEmpty);

  const submit = useCallback(async () => {
    if (!assignmentId || !trimmed) return;
    setSubmitting(true);
    setEmptySubmitHint(false);
    setError('');
    try {
      const res = await employeeAPI.postPolicyAssistantQuery(assignmentId, trimmed);
      const answer = res.answer;
      scrollToResponseAfterAnswerRef.current = true;
      setTurns((prev) => {
        const next = [
          ...prev,
          {
            id: newTurnId(),
            question: trimmed,
            answer,
            assistantRequestId: res.request_id ?? null,
          },
        ];
        const trimmedList = next.length > MAX_TURNS ? next.slice(-MAX_TURNS) : next;
        saveEmployeePolicyAssistantTurns(assignmentId, trimmedList);
        return trimmedList;
      });
      setMessage('');
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } }; message?: string };
      const d = ax.response?.data?.detail;
      setError(typeof d === 'string' ? d : ax.message || 'Could not load a policy answer. Try again.');
    } finally {
      setSubmitting(false);
    }
  }, [assignmentId, trimmed]);

  const applySuggestion = (q: string) => {
    setMessage(q);
    setError('');
    setEmptySubmitHint(false);
    focusQuestionInput();
  };

  const handlePrimaryAction = () => {
    if (!assignmentId || submitting) return;
    if (!message.trim()) {
      setEmptySubmitHint(true);
      focusQuestionInput();
      return;
    }
    setEmptySubmitHint(false);
    void submit();
  };

  const handleClearSavedHistory = () => {
    if (!assignmentId) return;
    setTurns([]);
    clearEmployeePolicyAssistantTurns(assignmentId);
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
    setEmptySubmitHint(false);
    focusQuestionInput();
  };

  const questionId =
    layoutVariant === 'sideSheet' ? 'policy-assistant-question-sheet' : 'policy-assistant-question';
  const shortcutsSectionId =
    layoutVariant === 'sideSheet' ? 'policy-assistant-shortcuts-sheet' : 'policy-assistant-shortcuts';

  const shortcuts = EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS.slice(0, 4);

  const questionDescribedBy = [shortcutsSectionId, emptySubmitHint ? 'policy-assistant-empty-hint' : '']
    .filter(Boolean)
    .join(' ');

  const errorParts = error ? policyAssistantUserFacingError(error) : null;

  const mainForm = (
    <>
      {layoutVariant !== 'sideSheet' ? (
        <header className="mb-8 space-y-1.5">
          <h2 className="text-lg font-semibold tracking-tight text-[#0b2b43]">
            {EMPLOYEE_POLICY_ASSISTANT_TITLE}
          </h2>
          <p className="text-xs text-slate-500 leading-relaxed max-w-md">
            {EMPLOYEE_POLICY_ASSISTANT_SUBTITLE}
          </p>
        </header>
      ) : null}

      <div className="flex flex-col gap-8">
        {/* Input + primary action */}
        <div className="flex flex-col gap-2" aria-busy={submitting}>
          <label htmlFor={questionId} className="sr-only">
            Policy question
          </label>
          <textarea
            ref={textareaRef}
            id={questionId}
            rows={6}
            maxLength={8000}
            placeholder={EMPLOYEE_POLICY_ASSISTANT_PLACEHOLDER}
            className="w-full resize-y min-h-[10rem] rounded-lg border border-slate-300/90 bg-white px-3.5 py-3.5 text-sm text-slate-800 leading-relaxed shadow-sm placeholder:text-slate-400 transition-[border-color,box-shadow] focus:outline-none focus:border-[#0b2b43]/50 focus:ring-2 focus:ring-[#0b2b43]/12 focus:shadow-[0_1px_2px_rgba(15,23,42,0.06)] disabled:opacity-60"
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              if (emptySubmitHint) setEmptySubmitHint(false);
            }}
            onFocus={() => {
              if (emptySubmitHint) setEmptySubmitHint(false);
            }}
            disabled={submitting}
            aria-describedby={questionDescribedBy}
          />
          <Button
            type="button"
            variant="primary"
            size="lg"
            fullWidth
            onClick={handlePrimaryAction}
            disabled={!assignmentId || submitting}
            className={`mt-1 font-semibold shadow-sm transition-colors ${
              buttonInactiveLook
                ? '!bg-slate-200 !text-slate-600 hover:!bg-slate-300/90 focus:!ring-slate-400/50 !shadow-none'
                : ''
            }`}
            aria-busy={submitting}
          >
            {submitting ? (
              <span className="inline-flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                Checking published policy…
              </span>
            ) : (
              EMPLOYEE_POLICY_ASSISTANT_SUBMIT
            )}
          </Button>
          {emptySubmitHint ? (
            <p
              id="policy-assistant-empty-hint"
              className="text-xs text-slate-500"
              role="status"
            >
              {EMPLOYEE_POLICY_ASSISTANT_EMPTY_HINT}
            </p>
          ) : null}
          {errorParts ? (
            <Alert variant="error" className="mt-0.5" title={errorParts.title}>
              {errorParts.detail ? (
                <span className="block leading-relaxed opacity-95">{errorParts.detail}</span>
              ) : null}
            </Alert>
          ) : null}
        </div>

        <section
          id={shortcutsSectionId}
          className="flex flex-col gap-2.5"
          aria-label={EMPLOYEE_POLICY_ASSISTANT_SHORTCUTS_TITLE}
        >
          <h3 className="text-xs font-medium text-slate-600">{EMPLOYEE_POLICY_ASSISTANT_SHORTCUTS_TITLE}</h3>
          <div className="flex flex-wrap gap-2">
            {shortcuts.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => applySuggestion(s)}
                disabled={submitting}
                className="inline-flex h-9 min-h-9 max-w-full items-center rounded-md border border-slate-200 bg-white px-3 py-0 text-left text-xs font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50 sm:max-w-[280px]"
              >
                {s}
              </button>
            ))}
          </div>
        </section>

        <div className="pt-1 border-t border-slate-200/80 space-y-1">
          <p className="text-[11px] leading-relaxed text-slate-400">{EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER}</p>
          <p className="text-[11px] leading-relaxed text-slate-400">{EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER_SECONDARY}</p>
        </div>

        {/* POLICY RESPONSE AREA — grounded policy output (not chat UI) */}
        <section
          ref={responseSectionRef}
          className="rounded-xl border border-slate-200/95 bg-slate-50/90 p-4 -mt-1 ring-1 ring-slate-200/60"
          aria-label="Published policy answer"
        >
          <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0 space-y-1">
              <h3 className="text-sm font-semibold text-[#0b2b43] tracking-tight">Answers from your policy</h3>
              {turns.length > 0 ? (
                <p className="text-[11px] leading-relaxed text-slate-500 max-w-[min(100%,22rem)]">
                  {EMPLOYEE_POLICY_ASSISTANT_SAVED_HINT}
                </p>
              ) : null}
            </div>
            {turns.length > 0 ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="shrink-0 border-slate-200 text-xs text-slate-600"
                onClick={handleClearSavedHistory}
              >
                {EMPLOYEE_POLICY_ASSISTANT_CLEAR_HISTORY}
              </Button>
            ) : null}
          </div>
          {turns.length > 0 ? (
            <div className="space-y-4">
              {[...turns].reverse().map((t) => (
                <AnswerResultCard
                  key={t.id}
                  question={t.question}
                  answer={t.answer}
                  assistantTurnRequestId={t.assistantRequestId}
                  onFollowUpSelect={handleFollowUpFromAnswer}
                />
              ))}
            </div>
          ) : (
            <div
              className="flex min-h-[4.5rem] flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-slate-200 bg-white px-3 py-6 text-center"
              aria-hidden
            >
              <span className="text-sm font-medium text-slate-500">No answers yet</span>
              <span className="text-xs text-slate-400 max-w-xs leading-relaxed">
                Ask a question above. Your answers will show here and stay on this device for this assignment.
              </span>
            </div>
          )}
        </section>
      </div>
    </>
  );

  if (assignmentLoading && !assignmentId) {
    if (layoutVariant === 'sideSheet') {
      return null;
    }
    return (
      <Card padding="md" className="mb-6 border-slate-200 bg-slate-50/40">
        <div className="text-base font-semibold text-[#0b2b43]">{EMPLOYEE_POLICY_ASSISTANT_TITLE}</div>
        <p className="text-sm text-slate-500 mt-2">Loading assignment for policy context…</p>
      </Card>
    );
  }

  if (!assignmentId) {
    if (layoutVariant === 'sideSheet') {
      return null;
    }
    return (
      <Card padding="md" className="mb-6 border-slate-200 bg-slate-50/50">
        <div className="text-base font-semibold text-[#0b2b43]">{EMPLOYEE_POLICY_ASSISTANT_TITLE}</div>
        <p className="text-sm text-slate-600 mt-1">{EMPLOYEE_POLICY_ASSISTANT_SUBTITLE}</p>
        <p className="text-sm text-slate-500 mt-3">{EMPLOYEE_POLICY_ASSISTANT_NO_ASSIGNMENT}</p>
      </Card>
    );
  }

  if (layoutVariant === 'sideSheet') {
    return (
      <PolicyAssistantSideSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        title={EMPLOYEE_POLICY_ASSISTANT_TITLE}
        subtitle={EMPLOYEE_POLICY_ASSISTANT_SUBTITLE}
        titleId="policy-assistant-sheet-title"
        trigger={
          <div className="sticky top-0 z-10 -mx-1 mb-4 flex flex-col items-end gap-1 bg-gradient-to-b from-white from-80% to-transparent pb-1 pt-1 px-1 sm:-mx-0">
            <Button
              type="button"
              variant="outline"
              className="shrink-0 border-slate-300 text-[#0b2b43] font-medium shadow-sm"
              onClick={() => setSheetOpen(true)}
            >
              {EMPLOYEE_POLICY_ASSISTANT_TITLE}
            </Button>
            <p className="hidden max-w-[15rem] text-right text-xs leading-snug text-slate-500 md:block">
              Opens as a side panel. This page stays open.
            </p>
          </div>
        }
      >
        {mainForm}
      </PolicyAssistantSideSheet>
    );
  }

  return <Card padding="md" className="mb-6 border-slate-200">{mainForm}</Card>;
};
