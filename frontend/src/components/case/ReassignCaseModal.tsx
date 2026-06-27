/**
 * AIQ-1136 (NAV-HR-2-FU): confirmation dialog for the HR "Reassign case" action
 * on the case-detail view. Lets HR hand a case to another HR in the same company.
 * Mirrors EscalateCaseModal's bespoke overlay pattern (there is no generic Modal
 * primitive) and composes PATCH /api/hr/cases/{case_id}/reassign-hr-owner. The
 * backend enforces company scoping on both the case and the target HR.
 */

import React, { useEffect, useState } from 'react';
import { Button, Card } from '../antigravity';
import { listCompanyHrTeam, reassignCaseHrOwner, type HrTeamMember } from '../../api/cases';

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  caseId: string;
  /** Shown in the header so HR knows which case they are reassigning. */
  caseLabel: string;
}

export const ReassignCaseModal: React.FC<Props> = ({ open, onClose, onSuccess, caseId, caseLabel }) => {
  const [team, setTeam] = useState<HrTeamMember[]>([]);
  const [loadingTeam, setLoadingTeam] = useState(false);
  const [hrUserId, setHrUserId] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadingTeam(true);
    setError(null);
    listCompanyHrTeam()
      .then((members) => {
        if (cancelled) return;
        const valid = members.filter((m) => m.profile_id);
        setTeam(valid);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load your HR team. Please try again.');
      })
      .finally(() => {
        if (!cancelled) setLoadingTeam(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const submit = async () => {
    if (!hrUserId) {
      setError('Pick the HR colleague who should own this case.');
      return;
    }
    if (!reason.trim()) {
      setError('Add a short reason — it is recorded on the case audit trail.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await reassignCaseHrOwner(caseId, { hr_user_id: hrUserId, reason: reason.trim() });
      setHrUserId('');
      setReason('');
      onSuccess();
    } catch {
      setError('Could not reassign the case. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const memberLabel = (m: HrTeamMember) => m.name || m.email || m.profile_id;

  return (
    // eslint-disable-next-line local/no-clickable-div, jsx-a11y/no-noninteractive-element-interactions -- role="dialog" is the correct ARIA role for the modal container; backdrop-click + Escape are the standard dismiss interactions
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reassign-case-title"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#0b2b43]/40 px-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && !submitting) onClose();
      }}
    >
      <Card padding="lg" className="w-full max-w-lg bg-white">
        <h3 id="reassign-case-title" className="text-lg font-semibold text-[#0b2b43]">
          Reassign case — {caseLabel}
        </h3>
        <p className="mt-2 text-sm text-[#4b5563]">
          Hand this case to another HR colleague in your company. They become the case owner; the
          change is recorded on the audit trail.
        </p>

        <label className="mt-4 block text-sm font-medium text-[#0b2b43]" htmlFor="reassign-hr">
          New owner
        </label>
        <select
          id="reassign-hr"
          value={hrUserId}
          onChange={(e) => setHrUserId(e.target.value)}
          disabled={submitting || loadingTeam}
          className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43] focus:border-[#0b2b43] focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
        >
          <option value="">{loadingTeam ? 'Loading…' : 'Select an HR colleague'}</option>
          {team.map((m) => (
            <option key={m.profile_id} value={m.profile_id}>
              {memberLabel(m)}
            </option>
          ))}
        </select>
        {!loadingTeam && team.length === 0 && !error && (
          <p className="mt-2 text-sm text-[#4b5563]">
            No other HR colleagues are set up in your company yet.
          </p>
        )}

        <label className="mt-4 block text-sm font-medium text-[#0b2b43]" htmlFor="reassign-reason">
          Reason
        </label>
        <textarea
          id="reassign-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="e.g. Going on leave — handing the DACH cases to Priya."
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
          <Button onClick={submit} disabled={submitting || loadingTeam}>
            {submitting ? 'Reassigning…' : 'Reassign case'}
          </Button>
        </div>
      </Card>
    </div>
  );
};
