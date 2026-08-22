/**
 * [AIQ-2088] Confirmation dialog for the HR "Close case" action.
 *
 * Mirrors EscalateCaseModal's bespoke-overlay pattern (there is no generic Modal
 * primitive) and composes POST /api/hr/assignments/{id}/close.
 *
 * WARNS, NEVER BLOCKS (decision, Romain, 2026-08-22). Outstanding RFQs and unfinished
 * milestones are shown so HR closes with their eyes open, and the backend records what
 * was outstanding in the audit event — but nothing here can refuse the close. HR knows
 * things the system does not: the employee left, the move was cancelled, the vendor was
 * paid offline. Refusing on system state is how you get cases that can never be closed,
 * which is the defect this ships to fix.
 *
 * Reason is OPTIONAL but asked for, because with no outcome column it is the only thing
 * that distinguishes a completed move from an abandoned one.
 */
import React, { useEffect, useState } from 'react';
import { Button, Card } from '../antigravity';
import {
  closeAssignment,
  getClosureReadiness,
  type ClosureReadiness,
} from '../../api/caseClosure';

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: (message: string) => void;
  /** The ASSIGNMENT id (`detail.id`), not the relocation-case UUID. */
  assignmentId: string;
  caseLabel: string;
}

export const CloseCaseModal: React.FC<Props> = ({
  open, onClose, onSuccess, assignmentId, caseLabel,
}) => {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<ClosureReadiness | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setReadiness(null);
    setError(null);
    // A readiness failure must not stop HR closing — the dialog just loses its warning.
    getClosureReadiness(assignmentId)
      .then((r) => { if (!cancelled) setReadiness(r); })
      .catch(() => { /* advisory only */ });
    return () => { cancelled = true; };
  }, [open, assignmentId]);

  if (!open) return null;

  const outstanding = readiness?.outstanding;
  const openRfqs = outstanding?.open_rfqs ?? 0;
  const openMilestones = outstanding?.incomplete_milestones ?? 0;
  const hasOutstanding = openRfqs > 0 || openMilestones > 0;

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await closeAssignment(assignmentId, reason);
      onSuccess(
        res.already_closed
          ? 'This case was already closed.'
          : 'Case closed — it no longer appears in your action list.',
      );
    } catch {
      setError('Could not close the case. Nothing was changed — try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <Card className="w-full max-w-lg p-6">
        <h2 className="text-lg font-semibold text-[#0b2b43]">Close this relocation</h2>
        <p className="mt-1 text-sm text-[#4b5563]">
          {caseLabel} — closing marks the relocation finished. It stays readable, and it
          drops out of your &ldquo;Needs your attention&rdquo; list.
        </p>

        {readiness?.already_closed && (
          <p className="mt-4 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5563]">
            This case is already closed.
          </p>
        )}

        {hasOutstanding && !readiness?.already_closed && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <p className="font-medium">Still open on this case</p>
            <ul className="mt-1 list-disc pl-5">
              {openRfqs > 0 && (
                <li>{openRfqs} vendor quote request{openRfqs === 1 ? '' : 's'} awaiting a reply</li>
              )}
              {openMilestones > 0 && (
                <li>{openMilestones} step{openMilestones === 1 ? '' : 's'} not marked done</li>
              )}
            </ul>
            <p className="mt-2">
              You can still close it — this is recorded on the case so the decision is auditable.
            </p>
          </div>
        )}

        <label className="mt-4 block text-sm font-medium text-[#0b2b43]" htmlFor="close-reason">
          Reason <span className="font-normal text-[#6b7280]">(optional)</span>
        </label>
        <textarea
          id="close-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="e.g. Employee arrived and completed local registration."
          className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
        />

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button onClick={submit} disabled={submitting}>
            {submitting ? 'Closing…' : 'Close case'}
          </Button>
        </div>
      </Card>
    </div>
  );
};
