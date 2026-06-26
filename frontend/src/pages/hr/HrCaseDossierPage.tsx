/**
 * [P4-2] HR Case Dossier Panel
 *
 * Route: /hr/cases/:caseId/dossier
 *
 * Shows all CaseForms for a case. Each row expands to reveal:
 *  - Status banner
 *  - History timeline (events)
 *  - Comment thread
 *  - Status change buttons (Approve / Reject / Reset / etc.)
 *  - Flag toggle
 *
 * Uses AppShell + max-w-5xl consistent with other HR pages.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '../../components/antigravity/Button';
import { AppShell } from '../../components/AppShell';
import { dossierAPI, type CaseFormSummary } from '../../api/dossier';
import { HrCaseFormRow } from '../../features/platform-v2/hr-dossier/HrCaseFormRow';
import {
  AddDocumentModal,
  type AddDocumentPersonOption,
} from '../../features/platform-v2/hr-dossier/AddDocumentModal';
import { buildRoute } from '../../navigation/routes';
import { useCaseFormsRealtime } from '../../hooks/useCaseFormsRealtime';

type FilterKey = 'all' | 'action_needed' | 'blocked' | 'flagged' | 'submitted';

const FILTER_TABS: Array<{ key: FilterKey; label: string }> = [
  { key: 'all',            label: 'All' },
  { key: 'action_needed',  label: 'Needs action' },
  { key: 'blocked',        label: 'Blocked' },
  { key: 'flagged',        label: 'Flagged' },
  { key: 'submitted',      label: 'Submitted / Done' },
];

function isUiBlocked(f: CaseFormSummary): boolean {
  return !!f.blocker_form_id && f.status !== 'submitted' && f.status !== 'approved' && f.status !== 'rejected';
}

function matchesFilter(f: CaseFormSummary & { flag_note?: string }, key: FilterKey): boolean {
  switch (key) {
    case 'all':           return true;
    case 'action_needed': return !isUiBlocked(f) && ['auto_filled','in_progress','pending_doc','ready'].includes(f.status);
    case 'blocked':       return isUiBlocked(f);
    case 'flagged':       return !!f.flag_note;
    case 'submitted':     return ['submitted','approved','rejected'].includes(f.status);
    default:              return true;
  }
}

export const HrCaseDossierPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [forms, setForms]     = useState<CaseFormSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [filter, setFilter]   = useState<FilterKey>('all');
  const [showAddDocument, setShowAddDocument] = useState(false);

  const load = useCallback(async () => {
    if (!caseId) { setError('Missing case id.'); setLoading(false); return; }
    setLoading(true);
    setError(null);
    try {
      const rows = await dossierAPI.list(caseId);
      setForms(rows);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || 'Failed to load forms');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { void load(); }, [load]);

  // Realtime: re-fetch when any case_form row changes
  useCaseFormsRealtime(caseId, () => void load());

  // Per-tab counts
  const counts = useMemo(() => ({
    all:           forms.length,
    action_needed: forms.filter((f) => matchesFilter(f as never, 'action_needed')).length,
    blocked:       forms.filter((f) => matchesFilter(f as never, 'blocked')).length,
    flagged:       forms.filter((f) => matchesFilter(f as never, 'flagged')).length,
    submitted:     forms.filter((f) => matchesFilter(f as never, 'submitted')).length,
  }), [forms]);

  const visible = useMemo(
    () => forms.filter((f) => matchesFilter(f as never, filter)),
    [forms, filter],
  );

  const overall = useMemo(() => {
    if (!forms.length) return { pct: 0, ready: 0, total: 0 };
    const pct   = Math.round(forms.reduce((s, f) => s + (f.completion_pct || 0), 0) / forms.length);
    const ready = forms.filter((f) => ['ready','submitted','approved'].includes(f.status)).length;
    return { pct, ready, total: forms.length };
  }, [forms]);

  // [P4-3] People the new document can be scoped to — derived from existing
  // forms' person field (employee/HR profiles), deduped by profile_id.
  const peopleOptions = useMemo<AddDocumentPersonOption[]>(() => {
    const byId = new Map<string, AddDocumentPersonOption>();
    for (const f of forms) {
      const id = f.person.profile_id;
      if (id && !byId.has(id)) {
        byId.set(id, { id, label: f.person.name || 'Employee' });
      }
    }
    return Array.from(byId.values());
  }, [forms]);

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* ── Header ────────────────────────────────────────────────────── */}
        <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase mb-1">
              ReloPass · HR Dossier
            </p>
            <h1 className="text-2xl font-semibold text-slate-900">Dossier panel</h1>
            <p className="text-sm text-slate-500 mt-1">
              All official forms for this case. Change status, flag issues, and annotate directly from here.
            </p>
          </div>

          <div className="flex items-center gap-4">
            {forms.length > 0 && (
              <div className="text-right">
                <div className="text-2xl font-semibold text-slate-900 leading-none">{overall.pct}%</div>
                <div className="text-xs text-slate-500 mt-1">
                  {overall.ready}/{overall.total} form{overall.total === 1 ? '' : 's'} ready · overall
                </div>
              </div>
            )}
            <div className="flex gap-2">
              <Button unstyled
                type="button"
                onClick={() => caseId && navigate(buildRoute('hrCaseSummary', { caseId }))}
                className="px-3 py-1.5 rounded text-sm font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                ← Case summary
              </Button>
              <Button unstyled
                type="button"
                onClick={() => setShowAddDocument(true)}
                className="px-3 py-1.5 rounded text-sm font-medium bg-[#0b2b43] text-white hover:bg-[#0e3a5c]"
              >
                + Add document
              </Button>
            </div>
          </div>
        </header>

        {/* ── Filter tabs ───────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-1 mb-4 border-b border-slate-200">
          {FILTER_TABS.map((tab) => {
            const isActive = filter === tab.key;
            return (
              <Button unstyled
                key={tab.key}
                type="button"
                onClick={() => setFilter(tab.key)}
                className={`relative px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? 'text-[#0b2b43]' : 'text-slate-500 hover:text-slate-700'
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
                {isActive && <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-[#0b2b43]" />}
              </Button>
            );
          })}
        </div>

        {/* ── Body ──────────────────────────────────────────────────────── */}
        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading forms…</div>
        ) : error ? (
          <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : visible.length === 0 ? (
          <div className="py-12 text-center text-slate-500">
            {forms.length === 0 ? 'No forms for this case yet.' : 'No forms match this filter.'}
          </div>
        ) : (
          <div className="grid gap-3">
            {visible.map((form) => (
              <HrCaseFormRow key={form.id} form={form} onRefresh={load} />
            ))}
          </div>
        )}
      </div>

      {/* [P4-3] Add-document modal */}
      {showAddDocument && caseId && (
        <AddDocumentModal
          caseId={caseId}
          people={peopleOptions}
          onClose={() => setShowAddDocument(false)}
          onCreated={() => void load()}
        />
      )}
    </AppShell>
  );
};
