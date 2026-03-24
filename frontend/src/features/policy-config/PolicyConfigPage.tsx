import React, { useMemo, useState } from 'react';
import { Alert, Card, Input } from '../../components/antigravity';
import { PolicyCategorySection } from './PolicyCategorySection';
import { PolicyConfigFilters } from './PolicyConfigFilters';
import { PolicyConfigHeader } from './PolicyConfigHeader';
import { PolicyConfigVersionHistoryDrawer } from './PolicyConfigVersionHistoryDrawer';
import { PolicyPublishConfirmModal } from './PolicyPublishConfirmModal';
import { usePolicyConfigWorkspace } from './usePolicyConfigWorkspace';
import { usePolicyConfigLeaveGuard } from './usePolicyConfigLeaveGuard';
import { normalizeCategoryBlocks } from './policyConfigUtils';
import { formatPolicyPreviewBanner } from './policyTargeting';
import { PolicyGlossarySection } from './PolicyGlossarySection';

export type PolicyConfigPageProps = {
  mode: 'hr' | 'admin';
  adminCompanyId?: string;
  hrCompanyIdOverride?: string | null;
};

export const PolicyConfigPage: React.FC<PolicyConfigPageProps> = ({
  mode,
  adminCompanyId,
  hrCompanyIdOverride,
}) => {
  const [assignmentType, setAssignmentType] = useState<string | null>(null);
  const [familyStatus, setFamilyStatus] = useState<string | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);

  const ws = usePolicyConfigWorkspace({
    mode,
    adminCompanyId,
    hrCompanyIdOverride,
  });

  usePolicyConfigLeaveGuard(ws.dirty && !ws.isReadOnly);

  const display = ws.displayPayload;
  const blocks = useMemo(
    () => normalizeCategoryBlocks(display?.categories),
    [display?.categories]
  );
  const canEditBenefits = !ws.isReadOnly && !ws.editingLocked;

  const publishPrecheck = useMemo(() => {
    const d = display;
    if (!d) return { publishAllowed: true, hint: '' };
    const hasEd = Boolean((d.effective_date || '').trim().slice(0, 10));
    const hasPv = Boolean((d.policy_version || '').trim());
    if (ws.dirty) return { publishAllowed: false, hint: 'Save draft before publishing.' };
    if (!hasPv) return { publishAllowed: false, hint: 'Create or open a draft first.' };
    if (!hasEd) return { publishAllowed: false, hint: 'Set an effective date on the draft before publishing.' };
    return { publishAllowed: true, hint: '' };
  }, [display, ws.dirty]);

  if (mode === 'admin' && !adminCompanyId) {
    return null;
  }

  const handlePublishConfirm = () => {
    setPublishOpen(false);
    void ws.publish();
  };

  return (
    <div className="space-y-6">
      {ws.error && (
        <Alert variant="error" title="Something went wrong">
          <pre className="text-xs whitespace-pre-wrap font-sans">{ws.error}</pre>
        </Alert>
      )}

      {ws.loading && !display ? (
        <Card padding="lg">
          <p className="text-[#64748b]">Loading policy configuration…</p>
        </Card>
      ) : !display ? (
        <Card padding="lg">
          <p className="text-[#64748b]">No data to display.</p>
        </Card>
      ) : (
        <>
          <PolicyConfigHeader
            meta={{
              status: display.status,
              source: display.source,
              version_number: display.version_number,
              effective_date: display.effective_date,
              published_at: display.published_at,
              created_at: display.created_at,
              updated_at: display.updated_at,
              policy_version: display.policy_version,
            }}
            readOnlySnapshot={ws.readOnlySnapshot}
            editingLocked={ws.editingLocked}
            dirty={ws.dirty}
            saving={ws.saving}
            publishing={ws.publishing}
            lastSavedAt={ws.lastSavedAt}
            onSaveDraft={() => ws.saveDraft()}
            onPublishClick={() => setPublishOpen(true)}
            onReload={() => ws.cancelChanges()}
            onViewPublished={() => ws.openPublishedView()}
            onBackToDraft={() => ws.backToDraft()}
            onOpenHistory={() => ws.openHistory()}
            onStartEditing={() => ws.startEditing()}
            publishAllowed={publishPrecheck.publishAllowed}
            publishDisabledHint={publishPrecheck.hint}
          />

          <PolicyPublishConfirmModal
            open={publishOpen}
            versionNumber={display.version_number}
            effectiveDate={display.effective_date}
            policyVersionId={display.policy_version}
            publishing={ws.publishing}
            onConfirm={handlePublishConfirm}
            onCancel={() => setPublishOpen(false)}
          />

          {!ws.isReadOnly && (
            <Card padding="lg" className="space-y-4">
              <h2 className="text-sm font-semibold text-[#0b2b43]">Effective date</h2>
              <p className="text-xs text-[#64748b]">
                Required before publish. Applies to this draft version; save the draft after changing it.
              </p>
              <div className="max-w-xs">
                <Input
                  label="Effective date"
                  type="date"
                  value={(display.effective_date || '').slice(0, 10)}
                  disabled={!canEditBenefits}
                  onChange={(v) => ws.setEffectiveDate(v)}
                />
                {ws.serverFieldErrors.effective_date && (
                  <p className="text-xs text-[#7a2a2a] mt-1">{ws.serverFieldErrors.effective_date}</p>
                )}
              </div>
            </Card>
          )}

          <PolicyGlossarySection />

          <Card padding="lg" className="space-y-4">
            <h2 className="text-sm font-semibold text-[#0b2b43]">Targeting preview</h2>
            <div className="rounded-lg border border-[#bfdbfe] bg-[#eff6ff] px-4 py-3 text-sm text-[#1e3a5f]">
              <p className="font-medium text-[#0b2b43]">{formatPolicyPreviewBanner(assignmentType, familyStatus)}</p>
            </div>
            <PolicyConfigFilters
              assignmentType={assignmentType}
              familyStatus={familyStatus}
              onAssignmentType={setAssignmentType}
              onFamilyStatus={setFamilyStatus}
              disabled={ws.isReadOnly}
            />
          </Card>

          <div className="space-y-4">
            {blocks.map((block) => (
              <PolicyCategorySection
                key={block.category_key}
                block={block}
                disabled={!canEditBenefits}
                assignmentTypeFilter={assignmentType}
                familyStatusFilter={familyStatus}
                onBenefitChange={ws.patchBenefit}
                serverErrorsByBenefitKey={ws.serverErrorsByBenefitKey}
              />
            ))}
          </div>
        </>
      )}

      <PolicyConfigVersionHistoryDrawer
        open={ws.historyOpen}
        onClose={ws.closeHistory}
        versions={ws.historyRows}
        loading={ws.historyLoading}
        onViewVersion={(id, meta) => ws.openHistoryVersion(id, meta)}
      />
    </div>
  );
};
