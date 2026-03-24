import React from 'react';
import { Button } from '../../components/antigravity';

type Props = {
  open: boolean;
  versionNumber: number | null | undefined;
  effectiveDate: string | undefined;
  policyVersionId: string | null | undefined;
  publishing: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export const PolicyPublishConfirmModal: React.FC<Props> = ({
  open,
  versionNumber,
  effectiveDate,
  policyVersionId,
  publishing,
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;

  const ed = (effectiveDate || '').slice(0, 10) || '—';
  const canPublish = Boolean(policyVersionId && ed && ed !== '—');

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Close publish dialog"
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="policy-publish-title"
        className="relative w-full max-w-md rounded-xl border border-[#e2e8f0] bg-white shadow-xl p-6 space-y-4"
      >
        <h2 id="policy-publish-title" className="text-lg font-semibold text-[#0b2b43]">
          Publish this policy?
        </h2>
        <p className="text-sm text-[#475569] leading-relaxed">
          Publishing will replace the current published compensation matrix for this company. The version you publish
          becomes <strong>read-only</strong>. Older published versions stay in <strong>version history</strong> as
          archived. A final check runs on all <strong>covered</strong> benefit rows (amounts, percentages, notes, and
          dependent allowances).
        </p>
        <ul className="text-sm text-[#334155] space-y-1 list-disc pl-5">
          <li>
            Draft version #<strong>{versionNumber ?? '—'}</strong>
          </li>
          <li>
            Effective date: <strong>{ed}</strong>
          </li>
          <li>Version id: <span className="font-mono text-xs">{policyVersionId || '—'}</span></li>
        </ul>
        {!canPublish && (
          <p className="text-sm text-[#7a2a2a]">Set an effective date and save the draft before publishing.</p>
        )}
        <div className="flex flex-wrap justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onCancel} disabled={publishing}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onConfirm} disabled={publishing || !canPublish}>
            {publishing ? 'Publishing…' : 'Publish now'}
          </Button>
        </div>
      </div>
    </div>
  );
};
