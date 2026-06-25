/**
 * [P1-6] Employee Roadmap page — /employee/case/:caseId/roadmap
 *
 * Renders the milestone-backed plan-view as the redesigned roadmap template
 * (dark hero + mini phase-timeline, "what you can do now", HR-handled banner,
 * collapsible phase sections). Header meta (cities / name / role / move date)
 * comes from the case-details endpoint; the plan + statuses from the plan-view.
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
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
import { buildRoute } from '../../navigation/routes';
import type { RelocationPlanPhaseTaskDTO } from '../../types/relocationPlanView';

export const EmployeeCaseRoadmapPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const selectionRef = useRef<HTMLDivElement>(null);
  const { selection, clear } = useTextSelection(selectionRef);

  const { data, loading, error } = useEmployeeRelocationPlanPageData(caseId);
  const runCta = useRelocationPlanCtaHandler(caseId ?? '', { resourceCaseId: data?.case_id });
  const handleCta = (t: RelocationPlanPhaseTaskDTO) => runCta(t.cta ?? null);

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

  const phaseBar = (
    <div className="mx-auto max-w-5xl px-6 pt-6">
      <PhaseContextBar
        phases={[
          { key: 'intake', label: 'Intake', status: 'done' },
          { key: 'services', label: 'Services & policy', status: 'done' },
          { key: 'roadmap', label: 'Roadmap', status: 'current' },
        ]}
        onSelect={(key) => {
          if (key === 'intake') navigate(buildRoute('employeeIntake'));
          if (key === 'services') navigate(buildRoute('services'));
        }}
      />
    </div>
  );

  if (loading && !data) {
    return (
      <AppShell>
        <div style={{ padding: '24px', color: 'var(--text-muted)' }}>Loading roadmap…</div>
      </AppShell>
    );
  }

  const isEmpty = !data || data.summary.total_tasks === 0 || data.phases.length === 0;
  if (error || isEmpty) {
    return (
      <AppShell>
        {phaseBar}
        <div className="mx-auto max-w-5xl px-6 py-6">
          <RoadmapBeingBuilt onMessageTeam={() => navigate(buildRoute('messages'))} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {phaseBar}
      <div ref={selectionRef} className="mx-auto max-w-5xl px-6 py-6">
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
