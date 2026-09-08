/**
 * Modal for an employee to ask HR to allow an over-cap service estimate.
 * T1.3 part 2 — pairs with backend POST /api/cases/{case_id}/exception-requests.
 */

import React, { useState } from 'react';
import { Button, Card } from '../../components/antigravity';
import {
  createExceptionRequest,
  type ExceptionRequest,
  type ExceptionCategory,
} from '../../api/exceptions';

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: (req: ExceptionRequest) => void;
  /** The case id the backend keys the row on. Must be a real case id — an assignment id
   *  fails require_case_access and 404s for an employee. */
  caseId: string;
  category: string;
  /** Human-friendly category label (e.g. "Housing"). */
  categoryLabel: string;
  /**
   * The amounts, expressed in `currency`. This modal does NO conversion and makes NO
   * assumption about the unit — it files exactly what the caller passes. These props were
   * previously named `…Usd` while the backend was sent a hardcoded 'USD', so a caller
   * handing over native-currency values (BenefitComparisonDashboard did) filed a 25,000 NOK
   * cap as $25,000 — ~10x, in the one field HR decides on.
   */
  requestedAmount: number;
  capAmount: number;
  /** ISO-4217 code the two amounts above are denominated in. Stored on the row; HR's inbox
   *  renders whatever this says, so it must be true. */
  currency: string;
  /**
   * Declared by the caller, never inferred. This used to be derived from `capAmount === 0`,
   * which silently mistyped any request whose cap simply hadn't resolved as a
   * 'new_category' ask. Only the caller knows whether the benefit is capped-and-exceeded
   * or absent from the package.
   */
  exceptionType: ExceptionCategory;
  /** Display amounts, pre-formatted by the caller in its own currency. */
  displayRequested: string;
  displayCap: string;
  /**
   * AIQ-1477: general "ask for more" mode — opened from the page-level CTA rather than a
   * specific over-cap row. Swaps the over-cap copy for general guidance and hides the
   * amount grid (which is meaningless without a specific cap). Default false.
   */
  generalRequest?: boolean;
}

export const RequestExceptionModal: React.FC<Props> = ({
  open,
  onClose,
  onSuccess,
  caseId,
  category,
  categoryLabel,
  requestedAmount,
  capAmount,
  currency,
  exceptionType,
  displayRequested,
  displayCap,
  generalRequest = false,
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
      // File exactly what the caller declared. Both `exceptionType` and `currency` used to
      // be decided here — the type inferred from `cap === 0`, the currency hardcoded 'USD' —
      // and both were wrong for any caller not working in USD. The caller owns the truth.
      const created = await createExceptionRequest(caseId, {
        category,
        exception_type: exceptionType,
        requested_amount: requestedAmount,
        cap_amount: capAmount,
        currency,
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
          {generalRequest ? 'Request an exception' : `Request exception — ${categoryLabel}`}
        </h3>
        <p className="mt-2 text-sm text-[#4b5563]">
          {generalRequest
            ? 'If a benefit doesn’t match your needs or isn’t covered by your policy, you can ask HR for an exception. Send a short reason and they will review and respond — you’ll see the decision on this page.'
            : 'Your shortlist for this category is over your HR policy cap. Send HR a short reason and they will approve or reject the request. You will see the decision on this page.'}
        </p>
        {!generalRequest && (
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
        )}
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
