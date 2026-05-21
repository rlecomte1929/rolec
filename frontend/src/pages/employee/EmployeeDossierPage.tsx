/**
 * [P1-5 / Phase 5A] Employee Dossier & Forms page.
 *
 * Lists all CaseForms (created automatically by the P1-3 Trigger Engine)
 * for the employee's current case. Each row is a CaseFormCard with status
 * badge, person, progress, and an expand-to-banner detail.
 *
 * Phase 5B (follow-up) will add the Supabase Realtime subscription that
 * makes newly-triggered forms appear without refresh, plus the overall
 * completion-% header tile and "Build dossier" CTA.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { dossierAPI, type CaseFormSummary } from '../../api/dossier';
import { CaseFormCard } from '../../features/platform-v2/dossier/CaseFormCard';
import { useCaseFormsRealtime } from '../../hooks/useCaseFormsRealtime';

type FilterTabKey = 'all' | 'action_needed' | 'blocked' | 'ready' | 'submitted';

const FILTER_TABS: Array<{ key: FilterTabKey; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'action_needed', label: 'Action needed' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'ready', label: 'Ready to submit' },
  { key: 'submitted', label: 'Submitted' },
];

function isUiBlocked(f: CaseFormSummary): boolean {
  return !!f.blocker_form_id && f.status !== 'submitted' && f.status !== 'approved' && f.status !== 'rejected';
}

function matchesFilter(f: CaseFormSummary, key: FilterTabKey): boolean {
  switch (key) {
    case 'all':           return true;
    case 'action_needed': return !isUiBlocked(f) && (f.status === 'auto_filled' || f.status === 'in_progress' || f.status === 'pending_doc');
    case 'blocked':       return isUiBlocked(f);
    case 'ready':         return !isUiBlocked(f) && f.status === 'ready';
    case 'submitted':     return f.status === 'submitted' || f.status === 'approved';
    default:              return true;
  }
}

export const EmployeeDossierPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const [forms, setForms] = useState<CaseFormSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterTabKey>('all');

  const load = useCallback(async () => {
    if (!caseId) {
      setError('Missing case id in URL.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rows = await dossierAPI.list(caseId);
      setForms(rows);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || 'Failed to load forms');
      setForms([]);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  // [P1-5B] Realtime: when the Trigger Engine creates a new case_form (or any
  // row updates — completion_pct, status flipping to submitted, etc.), refetch
  // the joined list so the new row + its template/person/field-summary appear.
  useCaseFormsRealtime(caseId, load);

  // [P1-5B] Overall completion %: simple average of per-form completion_pct
  // weighted equally. If no forms exist, 0%.
  const overall = useMemo(() => {
    if (forms.length === 0) return { pct: 0, ready: 0, total: 0 };
    const total = forms.length;
    const sum = forms.reduce((acc, f) => acc + (f.completion_pct || 0), 0);
    const pct = Math.round(sum / total);
    const ready = forms.filter(
      (f) => f.status === 'ready' || f.status === 'submitted' || f.status === 'approved',
    ).length;
    return { pct, ready, total };
  }, [forms]);

  // Per-filter counts for the tab labels — computed from the full list,
  // not the filtered view, so counts stay stable across tab clicks.
  const counts = useMemo(() => {
    return {
      all:           forms.length,
      action_needed: forms.filter((f) => matchesFilter(f, 'action_needed')).length,
      blocked:       forms.filter((f) => matchesFilter(f, 'blocked')).length,
      ready:         forms.filter((f) => matchesFilter(f, 'ready')).length,
      submitted:     forms.filter((f) => matchesFilter(f, 'submitted')).length,
    } as Record<FilterTabKey, number>;
  }, [forms]);

  const visible = useMemo(() => forms.filter((f) => matchesFilter(f, filter)), [forms, filter]);

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase mb-1">
              ReloPass · Dossier & Forms
            </p>
            <h1 className="text-2xl font-semibold text-slate-900">My dossier</h1>
            <p className="text-sm text-slate-500 mt-1 max-w-2xl">
              Every official form your relocation needs. Forms appear here automatically as your roadmap progresses.
            </p>
          </div>

          {/* [P1-5B] Completion summary + Build dossier CTA */}
          <div className="flex items-center gap-4">
            {forms.length > 0 && (
              <div className="text-right">
                <div className="text-2xl font-semibold text-slate-900 leading-none">
                  {overall.pct}%
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {overall.ready} of {overall.total} form{overall.total === 1 ? '' : 's'} ready · overall completion
                </div>
              </div>
            )}
            <button
              type="button"
              disabled
              title="Build dossier lands in P3-4 — coming soon"
              className="px-4 py-2 rounded text-sm font-medium bg-[#0b2b43] text-white opacity-50 cursor-not-allowed"
            >
              Build dossier
            </button>
          </div>
        </header>

        {/* Filter tabs */}
        <div className="flex flex-wrap items-center gap-1 mb-4 border-b border-slate-200">
          {FILTER_TABS.map((tab) => {
            const isActive = filter === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setFilter(tab.key)}
                className={`relative px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'text-[#0b2b43]'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {tab.label}
                <span
                  className={`ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-semibold ${
                    isActive ? 'bg-[#0b2b43] text-white' : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {counts[tab.key]}
                </span>
                {isActive && (
                  <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-[#0b2b43]" />
                )}
              </button>
            );
          })}
        </div>

        {/* Body */}
        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading your forms…</div>
        ) : error ? (
          <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : visible.length === 0 ? (
          <div className="py-12 text-center text-slate-500">
            {forms.length === 0
              ? 'No forms yet — they appear automatically as you complete your roadmap.'
              : 'No forms match this filter.'}
          </div>
        ) : (
          <div className="grid gap-3">
            {visible.map((form) => (
              <CaseFormCard key={form.id} form={form} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
};
