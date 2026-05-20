/**
 * usePolicyDraft — manages wizard state and draft persistence.
 *
 * - Wizard state lives in React state (not the DB) until an explicit save.
 * - saveDraft() calls PATCH /api/hr/policies/:id (or POST if no draftId yet).
 * - The hook also exposes loading / error / saved flash states for the UI.
 */
import { useState, useCallback, useRef } from 'react';
import type {
  RelocationPolicyJson,
  PolicyTier,
  PolicyBudgets,
  PolicyDocuments,
  PolicyVendorCategories,
  PolicyApprovalWorkflow,
} from '../../types/relocationPolicy';
import { createPolicy, updatePolicy } from '../../api/policyBuilder';

function emptyPolicy(): RelocationPolicyJson {
  return {
    tiers: [],
    budgets: {},
    documents: {},
    vendor_categories: {},
    approval_workflow: { auto_approve_under_cap: false },
  };
}

export type UsePolicyDraftReturn = {
  /** Current wizard JSON state */
  json: RelocationPolicyJson;
  /** ID of the saved draft in Supabase (null until first save) */
  draftId: string | null;
  /** True while a save is in flight */
  saving: boolean;
  /** True for 2 seconds after a successful save */
  savedFlash: boolean;
  /** Error message from last save attempt */
  saveError: string | null;

  // Dimension setters
  setTiers: (tiers: PolicyTier[]) => void;
  setBudgets: (budgets: PolicyBudgets) => void;
  setDocuments: (docs: PolicyDocuments) => void;
  setVendorCategories: (vc: PolicyVendorCategories) => void;
  setApprovalWorkflow: (aw: PolicyApprovalWorkflow) => void;

  /** Persist the current wizard state as a draft. */
  saveDraft: () => Promise<void>;
  /** Label for the draft (editable by HR). */
  label: string;
  setLabel: (label: string) => void;
};

export function usePolicyDraft(): UsePolicyDraftReturn {
  const [json, setJson] = useState<RelocationPolicyJson>(emptyPolicy());
  const [draftId, setDraftId] = useState<string | null>(null);
  const [label, setLabel] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerFlash = () => {
    setSavedFlash(true);
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    flashTimerRef.current = setTimeout(() => setSavedFlash(false), 2000);
  };

  const setTiers = useCallback(
    (tiers: PolicyTier[]) => setJson((j) => ({ ...j, tiers })),
    [],
  );
  const setBudgets = useCallback(
    (budgets: PolicyBudgets) => setJson((j) => ({ ...j, budgets })),
    [],
  );
  const setDocuments = useCallback(
    (documents: PolicyDocuments) => setJson((j) => ({ ...j, documents })),
    [],
  );
  const setVendorCategories = useCallback(
    (vendor_categories: PolicyVendorCategories) =>
      setJson((j) => ({ ...j, vendor_categories })),
    [],
  );
  const setApprovalWorkflow = useCallback(
    (approval_workflow: PolicyApprovalWorkflow) =>
      setJson((j) => ({ ...j, approval_workflow })),
    [],
  );

  const saveDraft = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    try {
      if (draftId) {
        await updatePolicy(draftId, { label: label || undefined, json_schema: json });
      } else {
        const res = await createPolicy({ label: label || undefined, json_schema: json });
        setDraftId(res.policy.id);
      }
      triggerFlash();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }, [draftId, json, label]);

  return {
    json,
    draftId,
    saving,
    savedFlash,
    saveError,
    setTiers,
    setBudgets,
    setDocuments,
    setVendorCategories,
    setApprovalWorkflow,
    saveDraft,
    label,
    setLabel,
  };
}
