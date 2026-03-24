import React from 'react';
import { Link } from 'react-router-dom';
import { Button, Badge, Select } from '../../../components/antigravity';
import type { AdminCompany } from '../../../types';
import type { PolicyConfigWorkingPayload } from '../../policy-config/types';
import { workspaceStatusBadge } from './policyWorkspaceModel';

function formatMetaDate(val: string | null | undefined): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return String(val);
  }
}

type Props = {
  companies: AdminCompany[];
  selectedCompanyId: string;
  onCompanyChange: (id: string) => void;
  onRefresh: () => void;
  loading: boolean;
  matrixPayload: PolicyConfigWorkingPayload | null;
  matrixLoading: boolean;
  sourceModeLabel: string;
  onCreateDraftFromPublished: () => void;
  draftActionLoading: boolean;
  onViewPublished: () => void;
  onSaveDraft: () => void;
  saveDraftDisabled: boolean;
  onPublishDraft: () => void;
  publishDisabled: boolean;
  savingDraft: boolean;
  publishingDraft: boolean;
  policyConfigHref: string;
  hrPolicyHref: string;
};

export const PolicyWorkspaceControls: React.FC<Props> = ({
  companies,
  selectedCompanyId,
  onCompanyChange,
  onRefresh,
  loading,
  matrixPayload,
  matrixLoading,
  sourceModeLabel,
  onCreateDraftFromPublished,
  draftActionLoading,
  onViewPublished,
  onSaveDraft,
  saveDraftDisabled,
  onPublishDraft,
  publishDisabled,
  savingDraft,
  publishingDraft,
  policyConfigHref,
  hrPolicyHref,
}) => {
  const badge = workspaceStatusBadge(matrixPayload);
  const badgeVariant = badge.tone === 'success' ? 'success' : badge.tone === 'warning' ? 'warning' : 'neutral';
  const versionLabel =
    matrixPayload?.version_number != null
      ? `v${matrixPayload.version_number}`
      : matrixPayload?.policy_version
        ? String(matrixPayload.policy_version).slice(0, 8) + '…'
        : '—';

  return (
    <div className="rounded-lg border border-[#e2e8f0] bg-white p-4 space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Select
          label="Company"
          value={selectedCompanyId}
          onChange={onCompanyChange}
          options={[
            { value: '', label: 'Select a company…' },
            ...companies.map((c) => ({ value: c.id, label: c.name })),
          ]}
          placeholder="Select a company…"
        />
        {selectedCompanyId ? (
          <>
            <Button onClick={onRefresh} disabled={loading || matrixLoading}>
              {loading || matrixLoading ? 'Refreshing…' : 'Refresh'}
            </Button>
            <Button variant="outline" onClick={onCreateDraftFromPublished} disabled={draftActionLoading}>
              {draftActionLoading ? 'Working…' : 'Create draft from published'}
            </Button>
            <Link
              to={policyConfigHref}
              className="inline-flex items-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 border-2 border-[#0b2b43] text-[#0b2b43] hover:bg-[#e6f2f4] focus:ring-[#0b2b43] px-4 py-2 text-base cursor-pointer"
            >
              New empty structured policy
            </Link>
            <Button variant="outline" onClick={onViewPublished} disabled={matrixLoading}>
              View published
            </Button>
            <Button variant="outline" onClick={onSaveDraft} disabled={saveDraftDisabled || savingDraft}>
              {savingDraft ? 'Saving…' : 'Save draft'}
            </Button>
            <Button onClick={onPublishDraft} disabled={publishDisabled || publishingDraft}>
              {publishingDraft ? 'Publishing…' : 'Publish draft'}
            </Button>
            <Link
              to={hrPolicyHref}
              className="inline-flex items-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 text-[#0b2b43] hover:bg-[#e6f2f4] focus:ring-[#0b2b43] px-4 py-2 text-base cursor-pointer"
            >
              HR policy documents
            </Link>
          </>
        ) : null}
      </div>

      {selectedCompanyId ? (
        <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-[#f1f5f9]">
          <span className="text-xs font-medium uppercase tracking-wide text-[#64748b]">Status</span>
          <Badge variant={badgeVariant} size="sm">
            {badge.label}
          </Badge>
          <span className="text-sm text-[#64748b]">
            Version <span className="text-[#0b2b43] font-medium">{versionLabel}</span>
            {' · '}
            Effective <span className="text-[#0b2b43] font-medium">{matrixPayload?.effective_date ?? '—'}</span>
            {' · '}
            Last updated <span className="text-[#0b2b43] font-medium">{formatMetaDate(matrixPayload?.updated_at)}</span>
            {' · '}
            Published at <span className="text-[#0b2b43] font-medium">{formatMetaDate(matrixPayload?.published_at)}</span>
            {' · '}
            Source mode <span className="text-[#0b2b43] font-medium">{sourceModeLabel}</span>
          </span>
        </div>
      ) : null}
    </div>
  );
};
