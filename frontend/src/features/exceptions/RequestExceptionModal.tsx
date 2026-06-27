/**
 * Modal for an employee to ask HR to allow an over-cap service estimate.
 * T1.3 part 2 — pairs with backend POST /api/cases/{case_id}/exception-requests.
 */

import React, { useState } from 'react';
import { Button, Card } from '../../components/antigravity';
import {
  createExceptionRequest,
  type ExceptionRequest,
} from '../../api/exceptions';

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: (req: ExceptionRequest) => void;
  /** Stable identifier the backend stores on the row. We pass assignment id for now. */
  caseId: string;
  category: string;
  /** Human-friendly category label (e.g. "Living Areas"). */
  categoryLabel: string;
  requestedAmountUsd: number;
  capAmountUsd: number;
  /** Display amounts (already converted from USD) so the modal shows familiar numbers. */
  displayRequested: string;
  displayCap: string;
}

export const RequestExceptionModal: React.FC<Props> = ({
  open,
  onClose,
  onSuccess,
  caseId,
  category,
  categoryLabel,
  requestedAmountUsd,
  capAmountUsd,
  displayRequested,
  displayCap,
}) => {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    if (!reason.trim()) {
      setError('Add a short reason so HR has context to decide.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      // Q3-A: derive the exception-type axis from the cap shape:
      //   cap = 0 → benefit not in the package, so this is a 'new_category' request
      //   cap > 0 → asking to exceed an existing cap → 'cap_override'
      // RequestExceptionModal only opens for over-cap or new-benefit service
      // estimates; timeline_extension / additional_coverage flow through other
      // surfaces (assignment-scoped, not this case-scoped endpoint).
      const exceptionType: 'new_category' | 'cap_override' =
        capAmountUsd === 0 ? 'new_category' : 'cap_override';
      const created = await createExceptionRequest(caseId, {
        category,
        exception_type: exceptionType,
        requested_amount: requestedAmountUsd,
        cap_amount: capAmountUsd,
        currency: 'USD',
        reason: reason.trim(),
      });
      onSuccess(created);
      setReason('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not submit the request.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    // eslint-disable-next-line local/no-clickable-div, jsx-a11y/no-noninteractive-element-interactions -- role="dialog" is the correct ARIA role for the modal container; backdrop-click + Escape are the standard dismiss interactions
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="request-exception-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b2b43]/40 px-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && !submitting) onClose();
      }}
    >
      <Card padding="lg" className="w-full max-w-lg bg-white">
        <h3 id="request-exception-title" className="text-lg font-semibold text-[#0b2b43]">
          Request exception — {categoryLabel}
        </h3>
        <p className="mt-2 text-sm text-[#4b5563]">
          Your shortlist for this category is over your HR policy cap. Send HR a short reason and
          they will approve or reject the request. You will see the decision on this page.
        </p>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-[#6b7280]">You are requesting</dt>
            <dd className="font-medium text-[#0b2b43]">{displayRequested}</dd>
          </div>
          <div>
            <dt className="text-[#6b7280]">Current cap</dt>
            <dd className="font-medium text-[#0b2b43]">{displayCap}</dd>
          </div>
        </dl>
        <label className="mt-4 block text-sm font-medium text-[#0b2b43]" htmlFor="exception-reason">
          Reason
        </label>
        <textarea
          id="exception-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          maxLength={2000}
          placeholder="e.g. High-cost city, family of 4 needs a 3-bed rental within 25 min commute."
          className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
          disabled={submitting}
        />
        {error && (
          <p role="alert" className="mt-2 text-sm text-[#b91c1c]">
            {error}
          </p>
        )}
        <div className="mt-5 flex flex-wrap items-center justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={submitting}>
            {submitting ? 'Sending…' : 'Send request to HR'}
          </Button>
        </div>
      </Card>
    </div>
  );
};
