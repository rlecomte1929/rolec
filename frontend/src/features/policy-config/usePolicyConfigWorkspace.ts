import { useCallback, useEffect, useMemo, useState } from 'react';
import { policyConfigMatrixAPI } from '../../api/client';
import type { PolicyConfigBenefitRow, PolicyConfigHistoryVersion, PolicyConfigWorkingPayload } from './types';
import {
  buildPutBody,
  normalizeCategoryBlocks,
  patchBenefitInPayload,
  upsertBenefitInPayload,
} from './policyConfigUtils';
import { validatePolicyConfigForPublish, validatePolicyConfigPayload } from './benefitRowValidation';
import { parsePolicyMatrixValidationDetail } from './policyMatrixApiErrors';

function normalizePayload(p: PolicyConfigWorkingPayload): PolicyConfigWorkingPayload {
  return {
    ...p,
    categories: normalizeCategoryBlocks(p.categories),
  };
}

function sigForDirty(p: PolicyConfigWorkingPayload | null): string {
  if (!p) return '';
  try {
    return JSON.stringify({
      pv: p.policy_version,
      ed: p.effective_date,
      cat: normalizeCategoryBlocks(p.categories),
    });
  } catch {
    return '';
  }
}

export type PolicyReadOnlySnapshot = {
  title: string;
  subtitle?: string;
  payload: PolicyConfigWorkingPayload;
};

export function usePolicyConfigWorkspace(args: {
  mode: 'hr' | 'admin';
  /** Required when mode === 'admin' */
  adminCompanyId: string | undefined;
  /** Optional HR admin override (query param) */
  hrCompanyIdOverride?: string | null;
}) {
  const { mode, adminCompanyId, hrCompanyIdOverride } = args;
  const hrQuery = hrCompanyIdOverride ?? undefined;

  const [payload, setPayload] = useState<PolicyConfigWorkingPayload | null>(null);
  const [baselineSig, setBaselineSig] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRows, setHistoryRows] = useState<PolicyConfigHistoryVersion[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [readOnlySnapshot, setReadOnlySnapshot] = useState<PolicyReadOnlySnapshot | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [serverErrorsByBenefitKey, setServerErrorsByBenefitKey] = useState<Record<string, string>>({});
  const [serverFieldErrors, setServerFieldErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setReadOnlySnapshot(null);
    setServerErrorsByBenefitKey({});
    setServerFieldErrors({});
    try {
      const raw =
        mode === 'admin'
          ? await policyConfigMatrixAPI.adminGet(adminCompanyId as string)
          : await policyConfigMatrixAPI.hrGet(hrQuery);
      const next = normalizePayload(raw as PolicyConfigWorkingPayload);
      setPayload(next);
      setBaselineSig(sigForDirty(next));
    } catch {
      setError('Unable to load policy configuration.');
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, [mode, adminCompanyId, hrQuery]);

  useEffect(() => {
    if (mode === 'admin' && !adminCompanyId) {
      setLoading(false);
      setPayload(null);
      setError(null);
      return;
    }
    void load().catch(() => undefined);
  }, [load, mode, adminCompanyId]);

  const isReadOnly = Boolean(readOnlySnapshot);

  const dirty = useMemo(() => {
    if (!payload || isReadOnly) return false;
    return sigForDirty(payload) !== baselineSig;
  }, [payload, baselineSig, isReadOnly]);

  const editingLocked = Boolean(payload && !payload.editable);

  const displayPayload = readOnlySnapshot?.payload ?? payload;

  const clearReadOnly = useCallback(() => {
    setReadOnlySnapshot(null);
  }, []);

  const patchBenefit = useCallback(
    (categoryKey: string, prev: PolicyConfigBenefitRow, next: PolicyConfigBenefitRow) => {
      const bk = next.benefit_key || prev.benefit_key;
      if (bk) {
        setServerErrorsByBenefitKey((m) => {
          if (!m[bk]) return m;
          const { [bk]: _, ...rest } = m;
          return rest;
        });
      }
      setPayload((p) => (p ? patchBenefitInPayload(p, categoryKey, prev, next) : p));
    },
    []
  );

  const upsertBenefit = useCallback(
    (categoryKey: string, prev: PolicyConfigBenefitRow | null, next: PolicyConfigBenefitRow) => {
      const bk = next.benefit_key || prev?.benefit_key;
      if (bk) {
        setServerErrorsByBenefitKey((m) => {
          if (!m[bk]) return m;
          const { [bk]: _, ...rest } = m;
          return rest;
        });
      }
      setPayload((p) => (p ? upsertBenefitInPayload(p, categoryKey, prev, next) : p));
    },
    []
  );

  const setEffectiveDate = useCallback((v: string) => {
    setServerFieldErrors((m) => {
      const next = { ...m };
      delete next.effective_date;
      return next;
    });
    setPayload((p) => (p ? { ...p, effective_date: v } : p));
  }, []);

  const saveDraft = useCallback(
    async (overridePayload?: PolicyConfigWorkingPayload): Promise<PolicyConfigWorkingPayload | null> => {
      const toSave = overridePayload ?? payload;
      if (!toSave?.policy_version) {
        setError('Create a draft before saving.');
        return null;
      }
      setSaving(true);
      setError(null);
      const rowErrors = validatePolicyConfigPayload(toSave);
      if (rowErrors.length) {
        setError(rowErrors.map((e) => e.message).join('\n'));
        setSaving(false);
        return null;
      }
      try {
        const body = buildPutBody(toSave);
        const raw =
          mode === 'admin'
            ? await policyConfigMatrixAPI.adminPutDraft(adminCompanyId as string, body)
            : await policyConfigMatrixAPI.hrPutDraft(body, hrQuery);
        const next = normalizePayload(raw as PolicyConfigWorkingPayload);
        setPayload(next);
        setBaselineSig(sigForDirty(next));
        setServerErrorsByBenefitKey({});
        setServerFieldErrors({});
        const ts = next.updated_at || next.created_at;
        if (ts) setLastSavedAt(ts);
        return next;
      } catch (err: unknown) {
        const ax = err as { response?: { data?: { detail?: unknown } } };
        const d = ax.response?.data?.detail;
        const parsed = parsePolicyMatrixValidationDetail(d);
        setServerErrorsByBenefitKey(parsed.byBenefitKey);
        setServerFieldErrors(parsed.byField);
        const msg =
          parsed.messages.length > 0
            ? parsed.messages.join('\n')
            : typeof d === 'string'
              ? d
              : 'Save failed.';
        setError(msg);
        return null;
      } finally {
        setSaving(false);
      }
    },
    [payload, mode, adminCompanyId, hrQuery]
  );

  const publish = useCallback(
    async (forValidation?: PolicyConfigWorkingPayload): Promise<PolicyConfigWorkingPayload | null> => {
    if (!payload?.policy_version) {
      setError('No draft to publish.');
      return null;
    }
    setPublishing(true);
    setError(null);
    const validateAgainst =
      forValidation && typeof forValidation === 'object'
        ? { ...forValidation, policy_version: payload.policy_version }
        : payload;
    const pubErrors = validatePolicyConfigForPublish(validateAgainst);
    if (pubErrors.length) {
      setError(`Fix validation issues before publishing:\n${pubErrors.map((e) => e.message).join('\n')}`);
      setPublishing(false);
      return null;
    }
    try {
      const body = { policy_version: payload.policy_version };
      const raw =
        mode === 'admin'
          ? await policyConfigMatrixAPI.adminPublish(adminCompanyId as string, body)
          : await policyConfigMatrixAPI.hrPublish(body, hrQuery);
      const next = normalizePayload(raw as PolicyConfigWorkingPayload);
      setPayload(next);
      setBaselineSig(sigForDirty(next));
      setReadOnlySnapshot(null);
      setServerErrorsByBenefitKey({});
      setServerFieldErrors({});
      const ts = next.published_at || next.updated_at;
      if (ts) setLastSavedAt(ts);
      return next;
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: unknown } } };
      const d = ax.response?.data?.detail;
      const parsed = parsePolicyMatrixValidationDetail(d);
      setServerErrorsByBenefitKey((prev) => ({ ...prev, ...parsed.byBenefitKey }));
      setServerFieldErrors((prev) => ({ ...prev, ...parsed.byField }));
      const msg =
        parsed.messages.length > 0
          ? parsed.messages.join('\n')
          : typeof d === 'string'
            ? d
            : 'Publish failed.';
      setError(msg);
      return null;
    } finally {
      setPublishing(false);
    }
  },
  [payload, mode, adminCompanyId, hrQuery]
);

  const startEditing = useCallback(async () => {
    setError(null);
    try {
      const raw =
        mode === 'admin'
          ? await policyConfigMatrixAPI.adminPostDraft(adminCompanyId as string)
          : await policyConfigMatrixAPI.hrPostDraft(hrQuery);
      const next = normalizePayload(raw as PolicyConfigWorkingPayload);
      setPayload(next);
      setBaselineSig(sigForDirty(next));
      setReadOnlySnapshot(null);
      setServerErrorsByBenefitKey({});
      setServerFieldErrors({});
    } catch {
      setError('Could not create or open a draft.');
    }
  }, [mode, adminCompanyId, hrQuery]);

  const openPublishedView = useCallback(async () => {
    setError(null);
    try {
      const data =
        mode === 'admin'
          ? await policyConfigMatrixAPI.adminPublished(adminCompanyId as string)
          : await policyConfigMatrixAPI.hrPublished(hrQuery);
      const view = normalizePayload(data as PolicyConfigWorkingPayload);
      if (!view.policy_version && (view.status === 'none' || view.categories?.length === 0)) {
        setError('No published version is available yet.');
        return;
      }
      setReadOnlySnapshot({
        title: 'Published version',
        subtitle: 'Read-only — what employees and caps APIs use today.',
        payload: view,
      });
    } catch {
      setError('Could not load published version.');
    }
  }, [mode, adminCompanyId, hrQuery]);

  const openHistoryVersion = useCallback(
    async (versionId: string, meta: Pick<PolicyConfigHistoryVersion, 'version_number' | 'status' | 'effective_date'>) => {
      setError(null);
      setHistoryOpen(false);
      try {
        const raw =
          mode === 'admin'
            ? await policyConfigMatrixAPI.adminGetVersion(adminCompanyId as string, versionId)
            : await policyConfigMatrixAPI.hrGetVersion(versionId, hrQuery);
        const view = normalizePayload(raw as PolicyConfigWorkingPayload);
        const st = (meta.status || '').toLowerCase();
        const title =
          st === 'archived' ? `Version ${meta.version_number} (archived)` : `Version ${meta.version_number} (published)`;
        setReadOnlySnapshot({
          title,
          subtitle: `Effective ${meta.effective_date || '—'} · Read-only snapshot from history`,
          payload: view,
        });
      } catch {
        setError('Could not load that version.');
      }
    },
    [mode, adminCompanyId, hrQuery]
  );

  const backToDraft = useCallback(() => {
    clearReadOnly();
  }, [clearReadOnly]);

  const openHistory = useCallback(async () => {
    setHistoryOpen(true);
    setHistoryLoading(true);
    try {
      const res =
        mode === 'admin'
          ? await policyConfigMatrixAPI.adminHistory(adminCompanyId as string)
          : await policyConfigMatrixAPI.hrHistory(hrQuery);
      setHistoryRows((res.versions || []) as PolicyConfigHistoryVersion[]);
    } catch {
      setHistoryRows([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [mode, adminCompanyId, hrQuery]);

  const closeHistory = useCallback(() => setHistoryOpen(false), []);

  /** Discard local edits by reloading from server */
  const cancelChanges = useCallback(() => {
    load();
  }, [load]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  return {
    payload,
    displayPayload,
    loading,
    error,
    setError,
    saving,
    publishing,
    dirty,
    editingLocked,
    isReadOnly,
    readOnlySnapshot,
    lastSavedAt,
    serverErrorsByBenefitKey,
    serverFieldErrors,
    load,
    saveDraft,
    publish,
    startEditing,
    cancelChanges,
    openPublishedView,
    openHistoryVersion,
    backToDraft,
    patchBenefit,
    upsertBenefit,
    setEffectiveDate,
    historyOpen,
    historyRows,
    historyLoading,
    openHistory,
    closeHistory,
  };
}
