import React, { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { Container } from '../../components/antigravity';
import {
  ImmigrationAnswerPanel,
  type ImmigrationCaseContext,
} from '../../features/immigration/ImmigrationAnswerPanel';
import { MoveAtAGlance } from '../../features/immigration/MoveAtAGlance';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { servicesAPI } from '../../api/client';

/**
 * Route: /employee/immigration-assistant
 * Employee-facing grounded immigration Q&A (AIQ-843 backend + AIQ-856 verdict capture).
 *
 * Slice 2: opens with a proactive "your move at a glance" panel (risk flags +
 * checklist) for the employee's own case, above the grounded Q&A.
 * Relocation-assistant MVP: resolve the employee's corridor from THEIR case (via the
 * services context) so the assistant pre-fills "your IN → DE move" instead of making
 * them hand-type From/To. Best-effort — if there's no assignment/corridor, the panel
 * falls back to the manual form.
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
        const ctx = await servicesAPI.getServicesContext(assignmentId);
        const from = ctx.case_context?.originCountry?.trim();
        const to = ctx.case_context?.destCountry?.trim();
        if (active && from && to) {
          setCaseContext({ from, to, label: `${from} → ${to}` });
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
  }, [assignmentId]);

  return (
    <AppShell title="Immigration Q&A" subtitle="Grounded, cited answers for your corridor">
      <Container maxWidth="xl" className="py-8 space-y-4">
        <MoveAtAGlance caseId={primaryCaseId} />
        {resolved ? (
          <ImmigrationAnswerPanel caseContext={caseContext} />
        ) : (
          <p className="text-sm text-slate-400">Loading your move details…</p>
        )}
      </Container>
    </AppShell>
  );
};
