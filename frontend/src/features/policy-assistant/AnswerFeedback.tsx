/**
 * End-user 👍/👎 helpfulness control for policy-assistant answers.
 *
 * Renders nothing when traceSessionId is absent (e.g. legacy answers or
 * server-side audit disabled). Posts to POST /api/policy-assistant/helpfulness
 * via submitHelpfulness(). Disables after a successful vote.
 */
import { useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { submitHelpfulness } from '../../api/policyHelpfulness';

export interface AnswerFeedbackProps {
  traceSessionId: string | null | undefined;
}

export function AnswerFeedback({ traceSessionId }: AnswerFeedbackProps) {
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(false);

  if (!traceSessionId) return null;

  async function vote(helpful: boolean) {
    if (submitted) return;
    setError(false);
    try {
      await submitHelpfulness(traceSessionId!, helpful, undefined);
      setSubmitted(true);
    } catch {
      setError(true);
    }
  }

  return (
    <div
      className="flex items-center gap-3 border-t border-gray-100 pt-3"
      data-testid="answer-feedback"
    >
      {submitted ? (
        <span className="text-xs text-slate-500">Thanks — feedback recorded.</span>
      ) : (
        <>
          <span className="text-xs text-slate-500">Was this helpful?</span>
          <Button variant="ghost" aria-label="Helpful" onClick={() => void vote(true)}>
            👍
          </Button>
          <Button variant="ghost" aria-label="Not helpful" onClick={() => void vote(false)}>
            👎
          </Button>
          {error && (
            <span className="text-xs text-red-500">Couldn&apos;t save — try again.</span>
          )}
        </>
      )}
    </div>
  );
}
