/**
 * HR Setup & Help Assistant panel — re-skin of HrPolicyAssistantPanel.
 *
 * Mirrors HrPolicyAssistantPanel's structure: message state, turns[], submit /
 * error / submitting, suggested starter chips, formatRichMessage for prose.
 * Two additions specific to this panel:
 *   1. Setup-progress summary at the top (from getSetupStatus()) — checklist
 *      of company profile / policy / first case / invite with done/pending indicators.
 *   2. Next-step button rendered after each answer (hidden when route is null).
 *
 * Designed for the `embedded` variant inside PolicyAssistantDockedShell
 * (parent provides title + close chrome), with a `card` variant as fallback.
 */
import React, { useCallback, useEffect, useId, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Circle } from 'lucide-react';
import { Alert, Button, Card } from '../../components/antigravity';
import { formatRichMessage } from '../../utils/richMessage';
import { getSetupStatus, askSetupAssistant } from '../../api/setupAssistant';
import type { SetupStatus, SetupAssistantAnswer } from '../../api/setupAssistant';

// ── Constants ───────────────────────────────────────────────────────────────

const SETUP_ASSISTANT_TITLE = 'Setup & Help Assistant';
const SETUP_ASSISTANT_SUBTITLE = 'Get guided help setting up your ReloPass workspace.';
const SETUP_ASSISTANT_TRUST_PILL = 'Answers grounded in your workspace state';
const SETUP_ASSISTANT_PLACEHOLDER = 'e.g. How do I publish a policy?';
const SETUP_ASSISTANT_SUBMIT = 'Ask';
const STARTER_CHIPS = [
  'How do I publish a policy?',
  "What's my next setup step?",
  'How do I invite an employee?',
] as const;

const MAX_TURNS = 5;

// ── Types ────────────────────────────────────────────────────────────────────

type Turn = {
  id: string;
  question: string;
  answer: SetupAssistantAnswer;
};

function newTurnId(): string {
  return `sa-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

// ── Setup-progress summary ───────────────────────────────────────────────────

function SetupProgressSummary({ status }: { status: SetupStatus }) {
  const steps = [
    { label: 'Company profile', done: status.company_profile_complete },
    { label: 'Policy published', done: status.policy_published },
    { label: 'First relocation case', done: status.cases_count > 0 },
    { label: 'Employee invited', done: status.employees_invited > 0 },
  ];
  const allDone = steps.every((s) => s.done);

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2.5 space-y-1.5">
      <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Setup progress</div>
      <ul className="space-y-1">
        {steps.map(({ label, done }) => (
          <li key={label} className="flex items-center gap-2 text-sm">
            {done ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
            ) : (
              <Circle className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
            )}
            <span className={done ? 'text-slate-700' : 'font-medium text-slate-900'}>
              {label}
            </span>
            {!done ? (
              <span className="ml-auto text-xs text-amber-700 font-medium">Pending</span>
            ) : null}
          </li>
        ))}
      </ul>
      {!allDone && status.next_step.label ? (
        <div className="pt-1 text-xs text-slate-500">
          <span className="font-semibold text-slate-700">Next: </span>
          {status.next_step.label}
        </div>
      ) : null}
    </div>
  );
}

// ── Answer card ──────────────────────────────────────────────────────────────

function SetupAnswerCard({
  question,
  answer,
  isMostRecent,
}: {
  question: string;
  answer: SetupAssistantAnswer;
  isMostRecent: boolean;
}) {
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(!isMostRecent);
  const reactId = useId();
  const bodyId = `sa-card-body-${reactId}`;

  useEffect(() => {
    setCollapsed(!isMostRecent);
  }, [isMostRecent]);

  const hasRoute = Boolean(answer.next_step?.route);

  return (
    <div
      className="rounded-lg border border-slate-200 bg-white shadow-sm"
      role="region"
      aria-label="Setup assistant answer"
    >
      {/* Collapsible header */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={!collapsed}
        aria-controls={bodyId}
        onClick={() => setCollapsed((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setCollapsed((v) => !v);
          }
        }}
        className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-2.5 bg-slate-50/80 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/30"
      >
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">Question</div>
          <p className="text-sm text-slate-800 mt-0.5">{question}</p>
        </div>
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-md text-slate-500" aria-hidden>
          <ArrowRight className={`h-4 w-4 transition-transform ${collapsed ? '' : 'rotate-90'}`} />
        </span>
      </div>

      {/* Body */}
      {collapsed ? null : (
        <div id={bodyId} className="px-4 py-3 space-y-3">
          {answer.error ? (
            <Alert variant="error">
              {answer.answer || 'Something went wrong. Please try again.'}
            </Alert>
          ) : (
            <div className="text-sm text-slate-800 leading-relaxed">
              {formatRichMessage(answer.answer)}
            </div>
          )}

          {/* Cited topics */}
          {isMostRecent && answer.cited_topics && answer.cited_topics.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {answer.cited_topics.map((t) => (
                <span
                  key={t}
                  className="inline-block rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs text-slate-600"
                >
                  {t}
                </span>
              ))}
            </div>
          ) : null}

          {/* Next-step button — hidden when route is null */}
          {isMostRecent && hasRoute && answer.next_step?.label ? (
            <Button
              type="button"
              onClick={() => {
                if (answer.next_step?.route) {
                  navigate(answer.next_step.route);
                }
              }}
              data-testid="setup-next-step-btn"
              className="mt-1"
            >
              {answer.next_step?.label}
              <ArrowRight className="ml-2 h-4 w-4" aria-hidden />
            </Button>
          ) : null}
        </div>
      )}
    </div>
  );
}

// ── Main panel ───────────────────────────────────────────────────────────────

export const SetupAssistantPanel: React.FC<{
  /**
   * `card` — full-width block with header (standalone usage).
   * `embedded` — caller provides chrome (PolicyAssistantDockedShell).
   */
  variant?: 'card' | 'embedded';
}> = ({ variant = 'card' }) => {
  const [message, setMessage] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Setup status
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [statusError, setStatusError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSetupStatus()
      .then((s) => { if (!cancelled) setSetupStatus(s); })
      .catch(() => { if (!cancelled) setStatusError(true); });
    return () => { cancelled = true; };
  }, []);

  const trimmed = message.trim();
  const canSubmit = Boolean(trimmed && !submitting);
  const inSheetLike = variant === 'embedded';

  const submit = useCallback(async () => {
    if (!trimmed) return;
    setSubmitting(true);
    setError('');
    try {
      const res = await askSetupAssistant(trimmed);
      setTurns((prev) => {
        const next = [...prev, { id: newTurnId(), question: trimmed, answer: res }];
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
            : (e as { message?: string }).message || 'Could not get an answer. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }, [trimmed]);

  const applySuggestion = (q: string) => {
    setMessage(q);
    setError('');
  };

  const questionId = inSheetLike ? 'sa-question-sheet' : 'sa-question';
  const isEmptyState = !message.trim() && turns.length === 0;

  const coreForm = (
    <>
      {/* Trust pill */}
      <div className={inSheetLike ? 'mt-0' : 'mt-2'}>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-900">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
          {SETUP_ASSISTANT_TRUST_PILL}
        </span>
      </div>

      {/* Setup-progress summary */}
      {setupStatus ? (
        <div className="mt-3">
          <SetupProgressSummary status={setupStatus} />
        </div>
      ) : statusError ? (
        <p className="mt-3 text-xs text-slate-500">
          Setup status unavailable.
        </p>
      ) : (
        <p className="mt-3 text-xs text-slate-500">Loading setup status…</p>
      )}

      {/* Empty-state starter chips */}
      {isEmptyState ? (
        <section className="mt-4 flex flex-col gap-3" aria-label="Suggested setup questions">
          <h3 className="text-sm font-semibold text-[#0b2b43] mb-1">Try one of these:</h3>
          <ul className="flex flex-col gap-2">
            {STARTER_CHIPS.map((s) => (
              <li key={s}>
                <Button unstyled
                  type="button"
                  onClick={() => applySuggestion(s)}
                  disabled={submitting}
                  className="flex w-full items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3.5 text-left text-sm font-medium text-slate-700 transition-colors hover:border-[#0b2b43]/25 hover:bg-slate-50 disabled:opacity-50"
                >
                  <span className="min-w-0 leading-snug">{s}</span>
                  <ArrowRight className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
                </Button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* Input + chips */}
      <div className="mt-4 space-y-2">
        <label htmlFor={questionId} className="sr-only">
          Setup question
        </label>
        <textarea
          id={questionId}
          rows={inSheetLike ? (isEmptyState ? 3 : 5) : 3}
          maxLength={4000}
          placeholder={SETUP_ASSISTANT_PLACEHOLDER}
          className={`w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-300 focus:border-slate-300 disabled:opacity-60${inSheetLike ? ' min-h-[5rem]' : ''}`}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          disabled={submitting}
        />
        {isEmptyState ? null : (
          <div className="flex flex-wrap gap-2">
            {STARTER_CHIPS.map((s) => (
              <Button unstyled
                key={s}
                type="button"
                onClick={() => applySuggestion(s)}
                disabled={submitting}
                className="text-left text-xs rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-slate-700 hover:bg-slate-100 disabled:opacity-50 max-w-full"
              >
                {s}
              </Button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-2 pt-1">
          <Button type="button" onClick={() => void submit()} disabled={!canSubmit}>
            {submitting ? 'Thinking…' : SETUP_ASSISTANT_SUBMIT}
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
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Answers</div>
          {[...turns].reverse().map((t, index) => (
            <SetupAnswerCard
              key={t.id}
              question={t.question}
              answer={t.answer}
              isMostRecent={index === 0}
            />
          ))}
        </div>
      ) : null}
    </>
  );

  if (variant === 'embedded') {
    return <>{coreForm}</>;
  }

  return (
    <Card padding="md" className="border-slate-200" id="setup-assistant">
      <div className="mb-1">
        <h2 className="text-base font-semibold text-[#0b2b43]">{SETUP_ASSISTANT_TITLE}</h2>
        <p className="text-sm text-slate-600 mt-0.5">{SETUP_ASSISTANT_SUBTITLE}</p>
      </div>
      {coreForm}
    </Card>
  );
};

export { SETUP_ASSISTANT_TITLE, SETUP_ASSISTANT_SUBTITLE, STARTER_CHIPS };
