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
import React, { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Button } from '../../components/antigravity/Button';
import { useValidatedParams, caseParamsSchema } from '../../hooks/useValidatedParams';
import { ROUTE_DEFS } from '../../navigation/routes';
import { AppShell } from '../../components/AppShell';
import { dossierAPI, type CaseFormSummary } from '../../api/dossier';
import { fetchRelocationPlanView } from '../../api/relocationPlanView';
import { Alert, isSourceStale } from '../../components/antigravity';
import { CaseFormCard } from '../../features/platform-v2/dossier/CaseFormCard';
import { isUiBlocked, isEffectivelyReady } from '../../features/platform-v2/dossier/dossierStatus';
import { useCaseFormsRealtime } from '../../hooks/useCaseFormsRealtime';

// AIQ-1264: lazy-load so the panel's API-client → supabase import chain isn't pulled
// into this page's static module graph (it threw "supabaseUrl is required" in the
// jsdom unit tests, which have no VITE_SUPABASE_* env).
const DossierSuggestionsPanel = lazy(() =>
  import('../../features/platform-v2/intake/DossierSuggestionsPanel').then((m) => ({
    default: m.DossierSuggestionsPanel,
  })),
);

// Same AIQ-1264 reason: DestinationRequirements imports api/cases → api/client →
// supabaseAuth → api/supabase, which calls createClient() at module scope and throws
// "supabaseUrl is required" under jsdom. Static-importing it broke all four of this
// page's unit tests. Lazy, like the panel above.
const DestinationRequirements = lazy(() =>
  import('../../features/platform-v2/dossier/DestinationRequirements').then((m) => ({
    default: m.DestinationRequirements,
  })),
);

// [AIQ-1821] Same AIQ-1264 reason again: this one imports api/client directly.
const RequirementsSufficiencyPanel = lazy(() =>
  import('../../features/platform-v2/dossier/RequirementsSufficiencyPanel').then((m) => ({
    default: m.RequirementsSufficiencyPanel,
  })),
);

type FilterTabKey = 'all' | 'action_needed' | 'blocked' | 'ready' | 'submitted';

const FILTER_TABS: Array<{ key: FilterTabKey; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'action_needed', label: 'Action needed' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'ready', label: 'Ready to submit' },
  { key: 'submitted', label: 'Submitted' },
];

function matchesFilter(f: CaseFormSummary, key: FilterTabKey): boolean {
  switch (key) {
    case 'all':           return true;
    // [AIQ-1250] a 100%-filled auto_filled form with no required docs is "ready",
    // not "action needed" — keep these chips consistent with the card badge.
    case 'action_needed': return !isUiBlocked(f) && !isEffectivelyReady(f) && (f.status === 'auto_filled' || f.status === 'in_progress' || f.status === 'pending_doc');
    case 'blocked':       return isUiBlocked(f);
    case 'ready':         return !isUiBlocked(f) && (f.status === 'ready' || isEffectivelyReady(f));
    case 'submitted':     return f.status === 'submitted' || f.status === 'approved';
    default:              return true;
  }
}

export const EmployeeDossierPage: React.FC = () => {
  const caseId = useValidatedParams(caseParamsSchema, {
    redirectTo: ROUTE_DEFS.employeeDashboard.path,
  })?.caseId;
  const [searchParams, setSearchParams] = useSearchParams();
  // [P1-6] When the Roadmap "Documents" chip links here it appends
  // ?roadmap_step=<stepId>; scope the list to that step's forms until cleared.
  const roadmapStep = searchParams.get('roadmap_step');
  const [forms, setForms] = useState<CaseFormSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterTabKey>('all');
  // [Validate gate] soft gate: until the roadmap is validated, lead with a nudge
  // and dim the forms. Optimistic-true so the gate never flashes before the
  // fetch resolves; fail-open on error (soft gate never blocks).
  const [roadmapValidated, setRoadmapValidated] = useState(true);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    fetchRelocationPlanView(caseId, { role: 'employee' })
      .then((p) => { if (!cancelled) setRoadmapValidated(!!p.roadmap_validated); })
      .catch(() => { if (!cancelled) setRoadmapValidated(true); });
    return () => { cancelled = true; };
  }, [caseId]);

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
  useCaseFormsRealtime(caseId, () => void load());

  // [P1-6] Forms in scope for the current view: when a roadmap step is active,
  // only its triggered forms; otherwise the full list. The status tabs,
  // counts, and completion summary all derive from this scoped set so the
  // page stays internally consistent with the banner.
  // [AIQ-1892] ?forms=<tok,tok> — a roadmap task whose dossier target is a SET of forms
  // rather than one. "Confirm family / dependent details" has no required_inputs to
  // build a single ?form= key from, and its forms are corridor-specific spouse/child
  // pairs (FAM-SPOUSE + FAM-CHILD, DEP-PARTNER + DEP-CHILD, AE-FAM-*, JP-DEP-*, …), so
  // ?form= could only ever expand one of them. Scope the list to every match instead.
  // Matching mirrors the ?form= predicate below (id / template code / substring).
  const formsGroupParam = searchParams.get('forms');
  const groupMatchedForms = useMemo(() => {
    const tokens = (formsGroupParam ?? '')
      .split(',')
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);
    if (tokens.length === 0) return null;
    const hits = forms.filter((f) =>
      tokens.some((v) => {
        if (f.id.toLowerCase() === v) return true;
        if ((f.template?.code ?? '').toLowerCase().includes(v)) return true;
        return v.length >= 4 && (f.template?.name ?? '').toLowerCase().includes(v);
      }),
    );
    // No match → null, so the employee sees the whole dossier rather than an empty
    // page. Same fail-open stance as the stale-?form= cleanup below.
    return hits.length > 0 ? hits : null;
  }, [formsGroupParam, forms]);

  const scopedForms = useMemo(() => {
    if (roadmapStep) return forms.filter((f) => f.roadmap_step_id === roadmapStep);
    return groupMatchedForms ?? forms;
  }, [forms, roadmapStep, groupMatchedForms]);

  const clearRoadmapStep = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    next.delete('roadmap_step');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  // [P1-5B] Overall completion %: simple average of per-form completion_pct
  // weighted equally. If no forms exist, 0%.
  const overall = useMemo(() => {
    if (scopedForms.length === 0) return { pct: 0, ready: 0, total: 0 };
    const total = scopedForms.length;
    const sum = scopedForms.reduce((acc, f) => acc + (f.completion_pct || 0), 0);
    const pct = Math.round(sum / total);
    const ready = scopedForms.filter(
      (f) =>
        f.status === 'ready' ||
        f.status === 'submitted' ||
        f.status === 'approved' ||
        isEffectivelyReady(f), // [AIQ-1250] count 100%-filled no-docs forms as ready
    ).length;
    return { pct, ready, total };
  }, [scopedForms]);

  // Per-filter counts for the tab labels — computed from the scoped list,
  // not the filtered view, so counts stay stable across tab clicks.
  const counts = useMemo(() => {
    return {
      all:           scopedForms.length,
      action_needed: scopedForms.filter((f) => matchesFilter(f, 'action_needed')).length,
      blocked:       scopedForms.filter((f) => matchesFilter(f, 'blocked')).length,
      ready:         scopedForms.filter((f) => matchesFilter(f, 'ready')).length,
      submitted:     scopedForms.filter((f) => matchesFilter(f, 'submitted')).length,
    };
  }, [scopedForms]);

  const visible = useMemo(
    () => scopedForms.filter((f) => matchesFilter(f, filter)),
    [scopedForms, filter],
  );

  // [AIQ-1252] Deep-link target: a roadmap "Start now" appends ?form=<key>. Match
  // it against a form's id, template code, a required-document key (roadmap upload
  // tasks reference supporting-doc keys), or a title substring. Best-effort —
  // resolves to null (no-op) when nothing matches.
  const formParam = searchParams.get('form');
  const matchedFormId = useMemo(() => {
    if (!formParam) return null;
    const v = formParam.trim().toLowerCase();
    if (!v) return null;
    const hit = forms.find((f) => {
      if (f.id.toLowerCase() === v) return true;
      if ((f.template?.code ?? '').toLowerCase() === v) return true;
      if ((f.template?.required_documents ?? []).some((d) => (d.key ?? '').toLowerCase() === v)) return true;
      const name = (f.template?.name ?? '').toLowerCase();
      return v.length >= 4 && name.includes(v);
    });
    return hit?.id ?? null;
  }, [formParam, forms]);

  // Scroll the matched card into view once forms have loaded. For a ?forms= group the
  // list is already scoped to the matches, so bring the first one into view — every
  // member is on screen, unlike ?form= where one card is singled out and expanded.
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const scrollTargetId = matchedFormId ?? groupMatchedForms?.[0]?.id ?? null;
  useEffect(() => {
    if (!scrollTargetId) return;
    const el = cardRefs.current[scrollTargetId];
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [scrollTargetId, visible]);

  // [AIQ-1319] A roadmap "Start now" can deep-link ?form=<docKey> for a document
  // (e.g. a passport upload) that has no corresponding form in this corridor's
  // dossier. Once forms have loaded and nothing matched, strip the stale param so
  // the employee lands cleanly on the dossier with no phantom highlight target,
  // instead of a URL that promises a form that isn't here.
  useEffect(() => {
    if (loading || !formParam || matchedFormId) return;
    const next = new URLSearchParams(searchParams);
    next.delete('form');
    setSearchParams(next, { replace: true });
  }, [loading, formParam, matchedFormId, searchParams, setSearchParams]);

  // [P2-08d] Count forms whose official source hasn't been verified within its
  // staleness threshold, so the user is warned at the dossier level before they
  // hit a per-form badge. Derived from the same scoped set as the other counts.
  const staleCount = useMemo(
    () => scopedForms.filter((f) => isSourceStale(f.template?.source_last_verified)).length,
    [scopedForms],
  );

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase mb-1">
              ReloPass · Dossier & Forms
            </p>
            <h1 className="text-2xl font-semibold text-slate-900">My dossier</h1>
            <p className="text-sm text-slate-500 mt-1 max-w-2xl">
              Every official form your relocation needs. Forms appear here automatically as your roadmap progresses.
            </p>
          </div>

          {/* [P1-5B] Completion summary. C-02 (AIQ-1245): the disabled "Build dossier"
              COMING SOON CTA was removed — employees act via the individual form cards
              (Open form / Download PDF); no placeholder primary CTA. */}
          {forms.length > 0 && (
            <div className="text-right">
              <div className="text-2xl font-semibold text-slate-900 leading-none">
                {overall.pct}%
              </div>
              {/* EMP-3: the % is fields filled, distinct from forms ready to submit —
                  label both so "83% / 0 ready" can't read as a contradiction. */}
              <div className="text-xs text-slate-500 mt-1">
                fields filled · {overall.ready} of {overall.total} form{overall.total === 1 ? '' : 's'} ready to submit
              </div>
            </div>
          )}
        </header>

        {/* M-06 (AIQ-1264): the AI suggested-questions panel was moved here from the
            intake Review step — it belongs where the employee works on their forms,
            not at the moment of submission. */}
        {caseId && (
          <Suspense fallback={null}>
            <div className="mb-6">
              <DossierSuggestionsPanel caseId={caseId} />
            </div>
          </Suspense>
        )}

        {/* [Validate gate] Soft gate: nudge the employee to validate their
            roadmap first. Forms below stay reachable (dimmed), never blocked. */}
        {!roadmapValidated && (
          <div
            data-testid="validate-roadmap-gate"
            className="mb-4 flex items-start gap-3 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4"
          >
            <span className="text-lg">🗺️</span>
            <div className="flex-1">
              <div className="text-sm font-semibold text-[#0b2b43]">Validate your roadmap to start</div>
              <div className="text-xs text-[#64748b] mt-0.5">
                Review your roadmap and click “Validate &amp; start tasks”. Your forms and uploads are below — they’ll be the focus once you’ve validated.
              </div>
              <Link
                to={`/employee/case/${caseId}/roadmap`}
                className="inline-block mt-2 text-xs font-semibold text-[#1f8e8b]"
              >
                Go to my roadmap →
              </Link>
            </div>
          </div>
        )}

        {/* What the destination actually requires — the missing half of this page.
            The forms below are how you SATISFY a requirement; until now nothing said
            what was required, or why. Nationality-gated, and it states a correct
            answer of "none" rather than leaving an empty pillar. */}
        {caseId && (
          <Suspense fallback={<div className="mb-6 text-sm text-[#6b7280]">Loading requirements…</div>}>
            <DestinationRequirements caseId={caseId} />
          </Suspense>
        )}

        {/* [AIQ-1821] The requirement FACTS an authority published and an admin approved,
            each with its source — plus, kept separate, the intake answers we still need.
            DestinationRequirements above says which requirement ITEMS apply; this says
            what the authorities actually wrote. Until now nothing rendered the approved
            facts at all: they reached an API no screen called. */}
        {caseId && (
          <Suspense fallback={<div className="mb-6 text-sm text-slate-500">Loading requirements on record…</div>}>
            <RequirementsSufficiencyPanel
              caseId={caseId}
              intakeHref={`/employee/case/${caseId}/intake`}
            />
          </Suspense>
        )}

        {/* Content-honesty disclaimer — form templates are representative, not
            legally verified, so always remind the employee to confirm with the
            issuing authority before submitting (per the design brief's content
            honesty rule). */}
        {forms.length > 0 && (
          <div data-testid="dossier-honesty-banner" className="mb-4">
            <Alert variant="warning">
              Indicative — always confirm details with the issuing authority before you submit.
              Forms shown here are representative and may differ from the latest official version.
            </Alert>
          </div>
        )}

        {/* [P1-6] Roadmap-step scope banner — shown when arriving from a
            roadmap Documents chip. Explains why the list is narrowed and
            lets the employee clear the filter. */}
        {roadmapStep && (
          <div
            data-testid="roadmap-step-filter-banner"
            className="mb-4 flex items-center justify-between gap-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
          >
            <span>Showing only documents from this roadmap step.</span>
            <Button unstyled
              type="button"
              onClick={clearRoadmapStep}
              className="shrink-0 font-medium text-amber-900 underline underline-offset-2 hover:text-amber-950"
            >
              Clear filter
            </Button>
          </div>
        )}

        {/* [P2-08d] Dossier-level stale-source overview banner. Additive: shows
            only when at least one in-scope form has an unverified source. */}
        {staleCount > 0 && (
          <div
            data-testid="stale-sources-banner"
            role="status"
            className="mb-4 flex items-start gap-2 rounded border border-[#e2d6bf] bg-[#f4efe5] px-3 py-2 text-sm text-[#7a5e2a]"
          >
            <svg className="mt-0.5 h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <span>
              {staleCount} form{staleCount === 1 ? '' : 's'} in your dossier{' '}
              {staleCount === 1 ? 'has a source' : 'have sources'} we haven&apos;t recently verified.
              Open the form to verify it directly at the official source.
            </span>
          </div>
        )}

        {/* Filter tabs */}
        <div className="flex flex-wrap items-center gap-1 mb-4 border-b border-slate-200">
          {FILTER_TABS.map((tab) => {
            const isActive = filter === tab.key;
            return (
              <Button unstyled
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
              </Button>
            );
          })}
        </div>

        {/* Body — dimmed (not blocked) until the roadmap is validated. */}
        <div className={roadmapValidated ? '' : 'opacity-60'}>
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
              <div
                key={form.id}
                ref={(el) => {
                  cardRefs.current[form.id] = el;
                }}
              >
                <CaseFormCard
                  form={form}
                  initialExpanded={form.id === matchedFormId}
                  highlight={form.id === matchedFormId}
                />
              </div>
            ))}
          </div>
        )}
        </div>
      </div>
    </AppShell>
  );
};
