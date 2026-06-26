/**
 * [P1-6] Employee Roadmap page — /employee/case/:caseId/roadmap
 *
 * Renders the milestone-backed plan-view as the redesigned roadmap template
 * (dark hero + mini phase-timeline, "what you can do now", HR-handled banner,
 * collapsible phase sections). Header meta (cities / name / role / move date)
 * comes from the case-details endpoint; the plan + statuses from the plan-view.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { PhaseContextBar } from '../../components/antigravity';
import { useTextSelection } from '../../hooks/useTextSelection';
import { ExplainTermPopover } from '../../features/explain/ExplainTermPopover';
import { RoadmapBeingBuilt } from '../../features/employee-journey/RoadmapBeingBuilt';
import { useEmployeeRelocationPlanPageData } from '../../features/relocation-plan-employee/useEmployeeRelocationPlanPageData';
import { useRelocationPlanCtaHandler } from '../../features/relocation-plan-employee/relocationPlanCtaNavigate';
import {
  RoadmapTemplate,
  type RoadmapHeaderMeta,
} from '../../features/relocation-plan-employee/roadmap-template/RoadmapTemplate';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';
import { validateRoadmap } from '../../api/cases';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';
import { useValidatedParams, caseParamsSchema } from '../../hooks/useValidatedParams';
import { resolveCaseStage, type StageState } from '../../features/employee-journey/caseStage';
import type { RelocationPlanPhaseTaskDTO } from '../../types/relocationPlanView';

export const EmployeeCaseRoadmapPage: React.FC = () => {
  const caseId = useValidatedParams(caseParamsSchema, {
    redirectTo: ROUTE_DEFS.employeeDashboard.path,
  })?.caseId;
  const navigate = useNavigate();
  const selectionRef = useRef<HTMLDivElement>(null);
  const { selection, clear } = useTextSelection(selectionRef);

  // H-08 (AIQ-1255): the page had no title — the browser tab + bookmarks were
  // unlabelled. Set a document title for the duration the page is mounted.
  useEffect(() => {
    const prev = document.title;
    document.title = 'Roadmap — ReloPass';
    return () => {
      document.title = prev;
    };
  }, []);

  const { data, loading, error, refetch, ensureDefaultsAndReload } =
    useEmployeeRelocationPlanPageData(caseId);
  const runCta = useRelocationPlanCtaHandler(caseId ?? '', { resourceCaseId: data?.case_id });
  const handleCta = (t: RelocationPlanPhaseTaskDTO) => {
    const documentInput = t.required_inputs.find((input) => input.type === 'document');
    if (caseId && t.cta?.type === 'upload_document' && documentInput?.key) {
      navigate(
        `${buildRoute('employeeCaseDossier', { caseId })}?form=${encodeURIComponent(documentInput.key)}`,
      );
      return;
    }
    runCta(t.cta ?? null);
  };

  // Header meta (cities / employee / role / move date) — separate endpoint.
  const [header, setHeader] = useState<RoadmapHeaderMeta | null>(null);
  useEffect(() => {
    const aid = (data?.assignment_id || caseId || '').trim();
    if (!aid) return;
    let cancelled = false;
    getCaseDetailsByAssignmentId(aid)
      .then((res) => {
        if (cancelled || !res.data) return;
        const c = res.data.case;
        const a = res.data.assignment;
        setHeader({
          originCity: c.originCity,
          destCity: c.destCity,
          destCountry: c.destCountry,
          targetMoveDate: c.targetMoveDate,
          employeeName: a.employee_full_name ?? undefined,
          role: c.draft?.assignmentContext?.jobTitle ?? undefined,
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [data?.assignment_id, caseId]);

  // Validate gate.
  const [localValidatedAt, setLocalValidatedAt] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const validated = !!data?.roadmap_validated || localValidatedAt !== null;
  const validatedAt = localValidatedAt ?? data?.roadmap_validated_at ?? null;
  const onValidate = async () => {
    if (!caseId || validating) return;
    setValidating(true);
    try {
      const res = await validateRoadmap(caseId);
      setLocalValidatedAt(res.roadmap_validated_at ?? new Date().toISOString());
    } finally {
      setValidating(false);
    }
  };

  // B1/B4: stage from the ONE shared resolver, not hardcoded — so this stepper can
  // never disagree with the dashboard / benefit-comparison steppers, and Services
  // is never falsely marked done. The roadmap page is gated to post-submit, so
  // intake is complete here; Services is only "done" when its flow truly completed
  // (no signal yet → reads as reachable, not complete).
  const stage = resolveCaseStage({ status: 'submitted', servicesComplete: false });
  const toBarStatus = (s: StageState): 'done' | 'current' | 'upcoming' =>
    s === 'done' ? 'done' : s === 'active' ? 'current' : 'upcoming';
  const phaseBar = (
    <div className="mx-auto max-w-5xl px-6 pt-6">
      <PhaseContextBar
        phases={[
          { key: 'intake', label: 'Intake', status: toBarStatus(stage.intake) },
          { key: 'services', label: 'Services & policy', status: toBarStatus(stage.services) },
          { key: 'roadmap', label: 'Roadmap', status: 'current' },
        ]}
        onSelect={(key) => {
          if (key === 'intake')
            navigate(
              caseId ? buildRoute('employeeCaseIntake', { caseId }) : buildRoute('employeeIntake'),
            );
          if (key === 'services') navigate(buildRoute('services'));
        }}
      />
    </div>
  );

  // ── Roadmap generation state machine ────────────────────────────────────────
  // generating → ready | empty | failed. The plan builds asynchronously after
  // submit (~60–90s), so an empty plan is polled for a bounded window before we
  // resolve to `empty` — it must never spin indefinitely.
  const POLL_MS = 4000;
  const GEN_TIMEOUT_MS = 60000;
  const [pollTimedOut, setPollTimedOut] = useState(false);
  const pollStartRef = useRef<number | null>(null);
  const planEmpty = !!data && data.summary.total_tasks === 0;
  const planReady = !!data && data.summary.total_tasks > 0 && data.phases.length > 0;

  useEffect(() => {
    if (loading || error) return;
    if (!planEmpty) {
      pollStartRef.current = null;
      if (pollTimedOut) setPollTimedOut(false);
      return;
    }
    if (pollStartRef.current === null) pollStartRef.current = Date.now();
    if (Date.now() - pollStartRef.current >= GEN_TIMEOUT_MS) {
      if (!pollTimedOut) setPollTimedOut(true);
      return;
    }
    const t = window.setTimeout(() => {
      void refetch();
    }, POLL_MS);
    return () => window.clearTimeout(t);
  }, [loading, error, planEmpty, data, refetch, pollTimedOut]);

  const retryGeneration = useCallback(() => {
    pollStartRef.current = null;
    setPollTimedOut(false);
    void ensureDefaultsAndReload();
  }, [ensureDefaultsAndReload]);

  const retryFetch = useCallback(() => {
    pollStartRef.current = null;
    setPollTimedOut(false);
    void refetch();
  }, [refetch]);

  if (loading && !data) {
    return (
      <AppShell>
        <div style={{ padding: '24px', color: 'var(--text-muted)' }}>Loading roadmap…</div>
      </AppShell>
    );
  }

  if (!planReady) {
    // error → failed; bounded poll elapsed with no tasks → empty; otherwise still generating.
    const variant: 'generating' | 'empty' | 'failed' = error
      ? 'failed'
      : planEmpty && pollTimedOut
        ? 'empty'
        : 'generating';
    return (
      <AppShell>
        {phaseBar}
        <div className="mx-auto max-w-5xl px-6 py-6">
          <RoadmapBeingBuilt
            variant={variant}
            onMessageTeam={() => navigate(buildRoute('messages'))}
            onRetry={variant === 'failed' ? retryFetch : variant === 'empty' ? retryGeneration : undefined}
          />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {phaseBar}
      <div ref={selectionRef} className="mx-auto max-w-5xl px-6 py-6">
        {/* H-08 (AIQ-1255): page heading so the employee has orientation above the hero. */}
        <h1 className="text-2xl font-semibold text-slate-900 mb-4">My roadmap</h1>
        <RoadmapTemplate
          data={data}
          header={header}
          caseId={caseId ?? ''}
          onCta={handleCta}
          validated={validated}
          validatedAt={validatedAt}
          validating={validating}
          onValidate={onValidate}
        />
      </div>
      {selection && (
        <ExplainTermPopover selection={selection} assignmentId={caseId ?? ''} onClose={clear} />
      )}
    </AppShell>
  );
};
