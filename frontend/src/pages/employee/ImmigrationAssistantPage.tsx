import React, { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { Container } from '../../components/antigravity';
import {
  ImmigrationAnswerPanel,
  type ImmigrationCaseContext,
} from '../../features/immigration/ImmigrationAnswerPanel';
import { MoveAtAGlance } from '../../features/immigration/MoveAtAGlance';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import api, { servicesAPI } from '../../api/client';

/**
 * Route: /employee/immigration-assistant
 * Unified relocation assistant (Slice 5): grounded Q&A spanning immigration ("what
 * does my move need") and company policy ("what does my company cover"). Also opens
 * with the proactive "your move at a glance" panel (Slice 2), passes the case id for
 * anonymised applicant context (Slice 3), and pre-fills the corridor from the case (MVP).
 */
export const ImmigrationAssistantPage: React.FC = () => {
  const { primaryCaseId, assignmentId } = useEmployeeAssignment();
  const [caseContext, setCaseContext] = useState<ImmigrationCaseContext | undefined>(undefined);
  const [resolved, setResolved] = useState(false);

  useEffect(() => {
    let active = true;
    if (!assignmentId) {
      setResolved(true);
      return;
    }
    void (async () => {
      try {
        // AIQ-1476: resolve the corridor AND the employee's nationality from intake
        // (already persisted + consent-gated) so the assistant doesn't ask the employee
        // to re-type what they gave in the intake form.
        const [ctx, nationalities] = await Promise.all([
          servicesAPI.getServicesContext(assignmentId),
          primaryCaseId
            ? api
                .get<{ profile: { nationality?: string | null; second_nationality?: string | null } | null }>(
                  `/api/employee/cases/${primaryCaseId}/profile`,
                )
                .then((r) =>
                  [r.data.profile?.nationality, r.data.profile?.second_nationality]
                    .map((n) => (n ?? '').trim())
                    .filter(Boolean),
                )
                .catch(() => [] as string[])
            : Promise.resolve([] as string[]),
        ]);
        const from = ctx.case_context?.originCountry?.trim();
        const to = ctx.case_context?.destCountry?.trim();
        if (active && from && to) {
          setCaseContext({ from, to, label: `${from} → ${to}`, nationalities });
        }
      } catch {
        // best-effort: fall back to the manual corridor form
      } finally {
        if (active) setResolved(true);
      }
    })();
    return () => {
      active = false;
    };
  }, [assignmentId, primaryCaseId]);

  return (
    <AppShell title="Relocation Assistant" subtitle="Grounded answers about your move and your company's benefits">
      <Container maxWidth="xl" className="py-8 space-y-4">
        <MoveAtAGlance caseId={primaryCaseId} />
        {resolved ? (
          <ImmigrationAnswerPanel caseId={primaryCaseId} caseContext={caseContext} />
        ) : (
          <p className="text-sm text-slate-400">Loading your move details…</p>
        )}
      </Container>
    </AppShell>
  );
};
