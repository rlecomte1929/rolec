import React from 'react';
import { AppShell } from '../../components/AppShell';
import { Container } from '../../components/antigravity';
import { ImmigrationAnswerPanel } from '../../features/immigration/ImmigrationAnswerPanel';
import { MoveAtAGlance } from '../../features/immigration/MoveAtAGlance';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';

/**
 * Route: /employee/immigration-assistant
 * Employee-facing grounded immigration Q&A (AIQ-843 backend + AIQ-856 verdict capture).
 *
 * Slice 2: opens with a proactive "your move at a glance" panel (risk flags +
 * checklist) for the employee's own case, above the grounded Q&A.
 */
export const ImmigrationAssistantPage: React.FC = () => {
  const { primaryCaseId } = useEmployeeAssignment();
  return (
    <AppShell title="Immigration Q&A" subtitle="Grounded, cited answers for your corridor">
      <Container maxWidth="xl" className="py-8 space-y-4">
        <MoveAtAGlance caseId={primaryCaseId} />
        <ImmigrationAnswerPanel />
      </Container>
    </AppShell>
  );
};
