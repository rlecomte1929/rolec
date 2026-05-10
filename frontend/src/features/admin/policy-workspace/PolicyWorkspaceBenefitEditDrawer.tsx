import React, { useCallback, useEffect, useState } from 'react';
import { Button, Input } from '../../../components/antigravity';
import { BenefitRowEditor } from '../../policy-config/BenefitRowEditor';
import type { PolicyConfigBenefitRow, PolicyConfigWorkingPayload } from '../../policy-config/types';
import { upsertBenefitInPayload } from '../../policy-config/policyConfigUtils';
import type { WorkspaceDisplayRow } from './policyWorkspaceModel';

function cloneRow(r: PolicyConfigBenefitRow): PolicyConfigBenefitRow {
  return {
    ...r,
    assignment_types: [...(r.assignment_types ?? [])],
    family_statuses: [...(r.family_statuses ?? [])],
    conditions_json: r.conditions_json && typeof r.conditions_json === 'object' ? { ...r.conditions_json } : {},
    cap_rule_json: r.cap_rule_json && typeof r.cap_rule_json === 'object' ? { ...r.cap_rule_json } : {},
  };
}

function stripWorkspaceVirtual(row: PolicyConfigBenefitRow): PolicyConfigBenefitRow {
  const { _workspace_virtual: _, ...rest } = row as WorkspaceDisplayRow;
  return rest;
}

type Props = {
  open: boolean;
  onClose: () => void;
  categoryKey: string;
  categoryLabel: string;
  row: WorkspaceDisplayRow | null;
  /** Snapshot when the drawer opened (used for upsert matching). */
  baselineRow: WorkspaceDisplayRow | null;
  readOnly: boolean;
  basePayload: PolicyConfigWorkingPayload | null;
  saveDraft: (override?: PolicyConfigWorkingPayload) => Promise<PolicyConfigWorkingPayload | null>;
  onRequestCreateDraft: () => Promise<void>;
  setWorkspaceError: (msg: string | null) => void;
  serverError?: string;
};

export const PolicyWorkspaceBenefitEditDrawer: React.FC<Props> = ({
  open,
  onClose,
  categoryKey,
  categoryLabel,
  row,
  baselineRow,
  readOnly,
  basePayload,
  saveDraft,
  onRequestCreateDraft,
  setWorkspaceError,
  serverError,
}) => {
  const [draft, setDraft] = useState<PolicyConfigBenefitRow | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !row) {
      setDraft(null);
      setLocalError(null);
      return;
    }
    setDraft(cloneRow(row));
    setLocalError(null);
  }, [open, row]);

  const persistReady = Boolean(basePayload?.policy_version);
  const disabledForm = readOnly || !draft || saving;

  const runSave = useCallback(
    async (stayOpen: boolean) => {
      setLocalError(null);
      setWorkspaceError(null);
      if (!draft || !basePayload) return;
      if (!persistReady) {
        setLocalError('Create a draft first (use “Create draft from published” or open a draft in this workspace).');
        return;
      }
      const cleaned = stripWorkspaceVirtual(draft);
      const merged = upsertBenefitInPayload(basePayload, categoryKey, baselineRow, cleaned);
      setSaving(true);
      try {
        const next = await saveDraft(merged);
        if (next && stayOpen && cleaned.benefit_key) {
          const block = next.categories?.find((c) => c.category_key === categoryKey);
          const updated = block?.benefits?.find((b) => b.benefit_key === cleaned.benefit_key);
          if (updated) setDraft(cloneRow(updated));
        }
        if (next && !stayOpen) onClose();
      } finally {
        setSaving(false);
      }
    },
    [
      draft,
      basePayload,
      persistReady,
      categoryKey,
      baselineRow,
      saveDraft,
      onClose,
      setWorkspaceError,
    ]
  );

  if (!open || !row || !draft) return null;

  const heading = (draft.benefit_label || draft.benefit_key || 'Benefit').trim() || 'Benefit';

  return (
    <div className="fixed inset-0 z-[60] flex justify-end" aria-modal="true" role="dialog">
      <button type="button" className="absolute inset-0 bg-black/30" aria-label="Close panel" onClick={onClose} />
      <div className="relative w-full max-w-lg h-full bg-white shadow-xl border-l border-[#e2e8f0] flex flex-col">
        <div className="p-4 border-b border-[#e2e8f0] flex justify-between items-start gap-2 shrink-0">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-[#64748b]">{categoryLabel}</p>
            <h3 className="text-lg font-semibold text-[#0b2b43] mt-0.5 leading-snug truncate" title={heading}>
              {readOnly ? `View: ${heading}` : `Edit: ${heading}`}
            </h3>
            {!persistReady && !readOnly ? (
              <p className="text-xs text-amber-900 mt-2 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
                No draft version yet. Create one to save changes from this workspace.
              </p>
            ) : null}
            {readOnly ? (
              <p className="text-xs text-[#64748b] mt-1">Published baseline is read-only. Open a draft to edit.</p>
            ) : null}
          </div>
          <Button size="sm" variant="ghost" onClick={onClose} disabled={saving}>
            Close
          </Button>
        </div>

        <div className="p-4 overflow-y-auto flex-1 min-h-0 space-y-4">
          {!readOnly && (
            <Input
              label="Benefit label"
              value={draft.benefit_label ?? ''}
              onChange={(v) => setDraft((d) => (d ? { ...d, benefit_label: v || undefined } : d))}
              disabled={disabledForm}
            />
          )}
          <BenefitRowEditor
            row={draft}
            disabled={disabledForm}
            onChange={setDraft}
            serverError={serverError}
          />
          {localError ? <p className="text-sm text-[#7a2a2a]">{localError}</p> : null}
        </div>

        {!readOnly && (
          <div className="p-4 border-t border-[#e2e8f0] space-y-2 shrink-0 bg-[#fafbfc]">
            {!persistReady ? (
              <Button type="button" className="w-full" onClick={() => onRequestCreateDraft().catch(() => undefined)}>
                Create draft to enable saving
              </Button>
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" className="flex-1 min-w-[7rem]" onClick={onClose} disabled={saving}>
                    Cancel
                  </Button>
                  <Button type="button" className="flex-1 min-w-[7rem]" onClick={() => runSave(false)} disabled={saving}>
                    {saving ? 'Saving…' : 'Save'}
                  </Button>
                </div>
                <Button type="button" variant="secondary" className="w-full" onClick={() => runSave(true)} disabled={saving}>
                  {saving ? 'Saving…' : 'Save & continue'}
                </Button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
