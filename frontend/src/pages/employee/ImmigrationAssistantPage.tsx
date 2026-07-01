import React, { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { Container } from '../../components/antigravity';
import {
  ImmigrationAnswerPanel,
  type ImmigrationCaseContext,
} from '../../features/immigration/ImmigrationAnswerPanel';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { servicesAPI } from '../../api/client';

/**
 * Route: /employee/immigration-assistant
 * Employee-facing grounded immigration Q&A (AIQ-843 backend + AIQ-856 verdict capture).
 *
 * Relocation-assistant MVP: resolve the employee's corridor from THEIR case (via the
 * services context) so the assistant pre-fills "your IN → DE move" instead of making
 * them hand-type From/To. Best-effort — if there's no assignment/corridor, the panel
 * falls back to the manual form. (Corridor codes pass through as-is; ISO-2
 * normalisation for the engine is a fast-follow.)
 */
export const ImmigrationAssistantPage: React.FC = () => {
  const { assignmentId } = useEmployeeAssignment();
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
      <Container maxWidth="xl" className="py-8">
        {resolved ? (
          <ImmigrationAnswerPanel caseContext={caseContext} />
        ) : (
          <p className="text-sm text-slate-400">Loading your move details…</p>
        )}
      </Container>
    </AppShell>
  );
};
