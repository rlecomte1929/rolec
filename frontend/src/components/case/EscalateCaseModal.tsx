/**
 * NAV-HR-2: confirmation dialog for the HR "Escalate case" action on the
 * case-detail view. Mirrors the bespoke overlay pattern (RequestExceptionModal /
 * PolicyPublishConfirmModal — there is no generic Modal primitive) and composes
 * the existing endpoint POST /api/hr/cases/{case_id}/escalate. Reason is
 * mandatory; the backend enforces company scoping + writes the audit trail.
 */

import React, { useState } from 'react';
import { Button, Card } from '../antigravity';
import { escalateCase, type EscalationKind } from '../../api/cases';

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  caseId: string;
  /** Shown in the header so HR knows which case they are escalating. */
  caseLabel: string;
}

const KIND_OPTIONS: { value: EscalationKind; label: string }[] = [
  { value: 'specialist', label: 'Specialist' },
  { value: 'legal', label: 'Legal' },
  { value: 'other', label: 'Other' },
];

export const EscalateCaseModal: React.FC<Props> = ({ open, onClose, onSuccess, caseId, caseLabel }) => {
  const [reason, setReason] = useState('');
  const [kind, setKind] = useState<EscalationKind>('specialist');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    if (!reason.trim()) {
      setError('Add a short reason — it is required so the specialist has context.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await escalateCase(caseId, { reason: reason.trim(), kind });
      setReason('');
      setKind('specialist');
      onSuccess();
    } catch {
      setError('Could not escalate the case. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="escalate-case-title"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#0b2b43]/40 px-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
    >
      <Card padding="lg" className="w-full max-w-lg bg-white">
        <h3 id="escalate-case-title" className="text-lg font-semibold text-[#0b2b43]">
          Escalate case — {caseLabel}
        </h3>
        <p className="mt-2 text-sm text-[#4b5563]">
          Send this case to a specialist or legal. They will be notified and can pick it up; you
          will see it as escalated on this page.
        </p>

        <label className="mt-4 block text-sm font-medium text-[#0b2b43]" htmlFor="escalate-kind">
          Route to
        </label>
        <select
          id="escalate-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value as EscalationKind)}
          disabled={submitting}
          className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
        >
          {KIND_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <label className="mt-4 block text-sm font-medium text-[#0b2b43]" htmlFor="escalate-reason">
          Reason
        </label>
        <textarea
          id="escalate-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          maxLength={1000}
          placeholder="e.g. Complex visa category — needs immigration counsel before the dossier deadline."
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
            {submitting ? 'Escalating…' : 'Escalate case'}
          </Button>
        </div>
      </Card>
    </div>
  );
};
