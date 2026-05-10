import React from 'react';
import { Alert, Button, Card } from '../../components/antigravity';
import { COMPARISON_TIER_HEADLINE } from './hrPolicyEmployeePreviewCompare';
import { COMPARISON_SUMMARY_COPY, type HrPolicyComparisonSummary } from './hrPolicyWorkspaceState';

export type PublishPreflightModalProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  publishBusy: boolean;
  /** Block confirm when normalized/review still loading */
  dataLoading: boolean;
  /** Active (published) source label, e.g. version number + template/upload */
  activeSummary: string;
  activeVersionLabel: string | null;
  activeComparison: HrPolicyComparisonSummary;
  /** Draft being published */
  draftSummary: string;
  draftVersionLabel: string | null;
  /** After publish, employees will see this comparison tier */
  comparisonAfterPublish: HrPolicyComparisonSummary;
  /** True when a published policy exists and this publish replaces it */
  willReplaceActive: boolean;
};

export const PublishPreflightModal: React.FC<PublishPreflightModalProps> = ({
  open,
  onClose,
  onConfirm,
  publishBusy,
  dataLoading,
  activeSummary,
  activeVersionLabel,
  activeComparison,
  draftSummary,
  draftVersionLabel,
  comparisonAfterPublish,
  willReplaceActive,
}) => {
  if (!open) return null;

  const warnPartial = comparisonAfterPublish === 'partial' || comparisonAfterPublish === 'informational';

  return (
    <div
      className="fixed inset-0 z-[60] bg-black/40 flex items-center justify-center p-4"
      role="presentation"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="publish-preflight-title"
        className="w-full max-w-lg"
        data-testid="publish-preflight-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <Card padding="lg" className="shadow-lg">
          <h2 id="publish-preflight-title" className="text-lg font-semibold text-[#0b2b43]">
            Ready to publish
          </h2>
          <p className="text-sm text-[#4b5563] mt-2">
            Employees continue seeing the current published policy until this publish action completes.
          </p>

          <div className="mt-4 space-y-3 text-sm text-[#374151] border-t border-[#e5e7eb] pt-3">
            <div>
              <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wide">Current active policy</div>
              <p className="mt-1">{activeSummary}</p>
              {activeVersionLabel && (
                <p className="text-xs text-[#6b7280] mt-0.5">Version: {activeVersionLabel}</p>
              )}
              <p className="text-xs text-[#6b7280] mt-1">
                Cost comparison today: <strong>{COMPARISON_TIER_HEADLINE[activeComparison]}</strong> —{' '}
                {COMPARISON_SUMMARY_COPY[activeComparison]}
              </p>
            </div>
            <div>
              <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wide">Draft you are publishing</div>
              <p className="mt-1">{draftSummary}</p>
              {draftVersionLabel && (
                <p className="text-xs text-[#6b7280] mt-0.5">Working version: {draftVersionLabel}</p>
              )}
            </div>
            <div>
              <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wide">After publish</div>
              <p className="mt-1">
                {willReplaceActive
                  ? 'This will replace the active published policy for employees (within eligibility).'
                  : 'This will become the first published policy employees can see.'}
              </p>
              <p className="mt-2 text-[#374151]">
                <strong>Employees will see this after publish</strong> — benefit limits from the version you publish.
              </p>
              <p className="text-xs text-[#6b7280] mt-1">
                Cost comparison after publish: <strong>{COMPARISON_TIER_HEADLINE[comparisonAfterPublish]}</strong> —{' '}
                {COMPARISON_SUMMARY_COPY[comparisonAfterPublish]}
              </p>
            </div>
          </div>

          {warnPartial && (
            <Alert variant="warning" className="mt-4">
              {comparisonAfterPublish === 'informational'
                ? 'Informational only: employees can read benefits, but automated cost comparison may stay limited until limits are complete.'
                : 'Cost comparison limited: some services will support full comparison; others stay descriptive until you finish a few limits.'}
            </Alert>
          )}

          <div className="mt-6 flex flex-wrap gap-3 justify-end">
            <Button variant="outline" onClick={onClose} disabled={publishBusy}>
              Cancel
            </Button>
            <Button
              onClick={() => void onConfirm()}
              disabled={publishBusy || dataLoading}
              title={dataLoading ? 'Wait for policy data to finish loading' : undefined}
            >
              {publishBusy ? 'Publishing…' : 'Confirm publish'}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};
