/**
 * [P5-3] PolicyAssistantPage — full-page policy Q&A with guided question tiles
 *
 * Layout:
 *   1. Scope label ("Ask about your relocation policy and benefits")
 *   2. 8 pre-populated question tiles in a 4×2 grid (hidden after first submit)
 *   3. Free-text input always visible
 *   4. Response cards with HR escalation button on each
 *   5. "New question" button (restores tiles after they've been hidden)
 *
 * Interaction contract:
 *   - Clicking a tile immediately submits it (no extra typing required)
 *   - Tiles disappear once the first question is submitted
 *   - "New question" restores tiles and clears the input
 *   - "Discuss with HR" on each response opens a pre-filled mailto draft
 *
 * The component is self-contained and does not wrap EmployeePolicyAssistantPanel;
 * it calls employeeAPI.postPolicyAssistantQuery directly, matching the same
 * API contract.
 */

import React, { useCallback, useRef, useState } from 'react';
import { ArrowRight, Download, Loader2, MessageSquare, RefreshCcw } from 'lucide-react';
import { Button } from '../../components/antigravity/Button';
import { employeeAPI } from '../../api/client';
import type { PolicyAssistantAnswer } from '../../types/policyAssistant';
import { AnswerFeedback } from '../policy-assistant/AnswerFeedback';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const SCOPE_LABEL = 'Ask about your relocation policy and benefits';

export const QUESTION_TILES: string[] = [
  'What is my housing allowance?',
  'How many home leave flights am I entitled to?',
  'Is international schooling covered for my children?',
  'What healthcare plan applies to my assignment?',
  'How is my cost-of-living adjustment calculated?',
  'Am I eligible for spouse support?',
  'What is the relocation assistance cap?',
  'How does tax equalisation work for my assignment?',
];

export const ESCALATION_SUBJECT_PREFIX = 'Policy question — relocation benefits';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AssistantTurn {
  id: string;
  question: string;
  answer: PolicyAssistantAnswer;
  /** Trace row id for the end-user helpfulness vote. Null when not available. */
  traceSessionId?: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function newTurnId(): string {
  return `pa-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Build a mailto: href with the question + assistant response pre-filled.
 * The HR admin's email is intentionally left blank (the `to` field is empty)
 * so the user's email client resolves it to their configured HR contact.
 */
export function buildEscalationHref(question: string, responseText: string): string {
  const subject = encodeURIComponent(ESCALATION_SUBJECT_PREFIX);
  const body = encodeURIComponent(
    `I asked: ${question}\n\nThe policy assistant responded: ${responseText}\n\nI would like to discuss this further.`,
  );
  return `mailto:?subject=${subject}&body=${body}`;
}

/**
 * Extract plain text from an answer for use in the HR escalation body.
 */
export function answerToPlainText(answer: PolicyAssistantAnswer): string {
  return (
    answer.answer_text?.trim() ||
    answer.refusal?.refusal_text?.trim() ||
    'No answer text available.'
  );
}

// ---------------------------------------------------------------------------
// QuestionTileGrid
// ---------------------------------------------------------------------------

interface QuestionTileGridProps {
  tiles: string[];
  disabled: boolean;
  onTileClick: (question: string) => void;
}

export function QuestionTileGrid({ tiles, disabled, onTileClick }: QuestionTileGridProps) {
  return (
    <div
      role="group"
      aria-label="Suggested policy questions"
      className="grid grid-cols-2 gap-3 sm:grid-cols-4"
      data-testid="question-tile-grid"
    >
      {tiles.map((tile) => (
        <Button unstyled
          key={tile}
          type="button"
          data-testid="question-tile"
          disabled={disabled}
          onClick={() => onTileClick(tile)}
          className="flex min-h-[5rem] flex-col items-start justify-between rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-left text-sm font-medium text-slate-700 shadow-sm transition-colors hover:border-[#0b2b43]/25 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/30 disabled:opacity-50"
        >
          <span className="leading-snug">{tile}</span>
          <ArrowRight className="mt-2 h-4 w-4 shrink-0 text-slate-400" aria-hidden />
        </Button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ResponseCard
// ---------------------------------------------------------------------------

interface ResponseCardProps {
  turn: AssistantTurn;
}

export function ResponseCard({ turn }: ResponseCardProps) {
  const plainResponse = answerToPlainText(turn.answer);
  const escalationHref = buildEscalationHref(turn.question, plainResponse);

  return (
    <article
      className="overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-sm"
      data-testid="response-card"
      aria-label="Policy Q&A"
    >
      {/* Question header */}
      <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 to-[#f4f7fb] px-4 py-3.5">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Your question
        </div>
        <p className="mt-1 text-[15px] font-medium leading-snug text-[#0b2b43]">
          {turn.question}
        </p>
      </div>

      {/* Answer body */}
      <div className="px-4 py-4 space-y-3">
        <div className="rounded-lg border border-slate-100 bg-slate-50/60 px-4 py-3.5 text-[15px] leading-relaxed text-slate-800">
          {plainResponse}
        </div>

        {/* Evidence list */}
        {turn.answer.evidence && turn.answer.evidence.length > 0 ? (
          <details className="rounded-lg border border-slate-200/80 bg-white" open>
            <summary className="cursor-pointer list-none px-3 py-2.5 text-xs font-semibold text-slate-600">
              Where this comes from
            </summary>
            <ul className="space-y-2 border-t border-slate-100 px-3 py-3">
              {turn.answer.evidence.map((ev, i) => (
                <li key={i} className="border-l-[3px] border-[#0b2b43]/25 pl-3">
                  <div className="text-sm font-semibold text-[#0b2b43]">
                    {ev.label || 'Policy source'}
                  </div>
                  {ev.excerpt ? (
                    <div className="mt-1 text-sm leading-relaxed text-slate-600">
                      {ev.excerpt}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        {/* HR escalation button */}
        <a
          href={escalationHref}
          data-testid="escalation-button"
          aria-label="Discuss this with HR"
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-600 shadow-sm transition-colors hover:border-[#0b2b43]/25 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/30"
        >
          <MessageSquare className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
          Discuss with HR →
        </a>

        {/* End-user helpfulness vote */}
        <AnswerFeedback traceSessionId={turn.traceSessionId} />
      </div>
    </article>
  );
}

// ---------------------------------------------------------------------------
// PolicyAssistantPage
// ---------------------------------------------------------------------------

export interface PolicyAssistantPageProps {
  assignmentId: string | null | undefined;
}

export const PolicyAssistantPage: React.FC<PolicyAssistantPageProps> = ({ assignmentId }) => {
  const [message, setMessage] = useState('');
  const [turns, setTurns] = useState<AssistantTurn[]>([]);
  const [showTiles, setShowTiles] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const responsesRef = useRef<HTMLDivElement>(null);

  const submit = useCallback(
    async (question: string) => {
      if (!assignmentId || !question.trim() || submitting) return;

      setSubmitting(true);
      setError('');
      // Hide tiles permanently once the first question is submitted
      setShowTiles(false);

      try {
        const res = await employeeAPI.postPolicyAssistantQuery(
          assignmentId,
          question.trim(),
        );
        setTurns((prev) => [
          {
            id: newTurnId(),
            question: question.trim(),
            answer: res.answer,
            traceSessionId: res.trace_session_id ?? null,
          },
          ...prev,
        ]);
        setMessage('');
        // Scroll response area into view
        window.setTimeout(() => {
          responsesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 50);
      } catch (e: unknown) {
        const ax = e as { response?: { data?: { detail?: string } }; message?: string };
        const detail = ax.response?.data?.detail;
        setError(
          typeof detail === 'string'
            ? detail
            : ax.message || "Couldn't get a policy answer. Please try again.",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [assignmentId, submitting],
  );

  const handleTileClick = (question: string) => {
    setMessage(question);
    void submit(question);
  };

  const handleSubmit = () => {
    void submit(message);
  };

  const handleExport = useCallback(async () => {
    if (!assignmentId || turns.length === 0 || exporting) return;
    setExporting(true);
    try {
      const exportTurns = turns.map((t) => ({
        question: t.question,
        answer_text: t.answer.answer_text?.trim() || t.answer.refusal?.refusal_text?.trim() || '',
        evidence: (t.answer.evidence ?? []).map((ev) => ({
          label: ev.label ?? undefined,
          excerpt: ev.excerpt ?? undefined,
        })),
      }));
      const blob = await employeeAPI.exportPolicySessionPdf(assignmentId, exportTurns);
      const today = new Date().toISOString().slice(0, 10);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `ReloPass_Policy_QA_${today}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      // Silent — PDF export failure is non-blocking
    } finally {
      setExporting(false);
    }
  }, [assignmentId, turns, exporting]);

  const handleNewQuestion = () => {
    setMessage('');
    setShowTiles(true);
    setError('');
    window.setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !submitting) {
      e.preventDefault();
      void submit(message);
    }
  };

  const noAssignment = !assignmentId;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 space-y-8" data-testid="policy-assistant-page">
      {/* Page header */}
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight text-[#0b2b43]">
          Policy Assistant
        </h1>
        <p className="text-sm text-slate-500" data-testid="scope-label">
          {SCOPE_LABEL}
        </p>
      </header>

      {noAssignment ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-6 py-8 text-center">
          <p className="text-sm font-medium text-slate-600">
            Link an active assignment to use the policy assistant.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Question tiles — hidden after first submit */}
          {showTiles ? (
            <QuestionTileGrid
              tiles={QUESTION_TILES}
              disabled={submitting}
              onTileClick={handleTileClick}
            />
          ) : null}

          {/* Action bar — shown when tiles are hidden and at least one turn exists */}
          {!showTiles && turns.length > 0 ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button unstyled
                type="button"
                data-testid="new-question-button"
                onClick={handleNewQuestion}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/30"
              >
                <RefreshCcw className="h-4 w-4 shrink-0" aria-hidden />
                New question
              </Button>

              <Button unstyled
                type="button"
                data-testid="export-pdf-button"
                disabled={exporting}
                onClick={() => void handleExport()}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/30 disabled:opacity-50"
                aria-label="Export session as PDF"
              >
                {exporting ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden />
                ) : (
                  <Download className="h-4 w-4 shrink-0" aria-hidden />
                )}
                {exporting ? 'Generating PDF…' : 'Export session'}
              </Button>
            </div>
          ) : null}

          {/* Text input */}
          <div className="space-y-2">
            <label htmlFor="policy-question-input" className="sr-only">
              Policy question
            </label>
            <textarea
              ref={inputRef}
              id="policy-question-input"
              data-testid="question-input"
              rows={showTiles ? 3 : 5}
              maxLength={8000}
              placeholder={showTiles ? 'Or type your own question…' : 'Type a follow-up question…'}
              value={message}
              disabled={submitting || noAssignment}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full resize-y rounded-lg border border-slate-300/90 bg-white px-3.5 py-3.5 text-sm text-slate-800 leading-relaxed shadow-sm placeholder:text-slate-400 transition-[border-color,box-shadow] focus:outline-none focus:border-[#0b2b43]/50 focus:ring-2 focus:ring-[#0b2b43]/12 disabled:opacity-60"
            />

            <Button unstyled
              type="button"
              data-testid="submit-button"
              disabled={!message.trim() || submitting || noAssignment}
              onClick={handleSubmit}
              className="w-full rounded-lg bg-[#0b2b43] py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#08213a] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/50 disabled:opacity-50"
              aria-busy={submitting}
            >
              {submitting ? (
                <span className="inline-flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Checking published policy…
                </span>
              ) : (
                'Ask'
              )}
            </Button>

            {error ? (
              <div
                role="alert"
                data-testid="error-message"
                className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
              >
                {error}
              </div>
            ) : null}
          </div>

          {/* Response cards */}
          {turns.length > 0 ? (
            <div ref={responsesRef} className="space-y-4" aria-label="Policy answers">
              {turns.map((turn) => (
                <ResponseCard key={turn.id} turn={turn} />
              ))}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default PolicyAssistantPage;
