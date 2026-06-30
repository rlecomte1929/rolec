import React from 'react';
import { AppShell } from '../../components/AppShell';
import { Container } from '../../components/antigravity';
import { ImmigrationAnswerPanel } from '../../features/immigration/ImmigrationAnswerPanel';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';

/**
 * Route: /employee/immigration-assistant
 * Employee-facing grounded immigration Q&A (AIQ-843 backend + AIQ-856 verdict capture).
 *
 * Slice 3: passes the employee's own case id so answers are tailored to their
 * anonymised applicant context (family situation) — ownership verified server-side.
 */
export const ImmigrationAssistantPage: React.FC = () => {
  const { primaryCaseId } = useEmployeeAssignment();
  return (
    <AppShell title="Immigration Q&A" subtitle="Grounded, cited answers for your corridor">
      <Container maxWidth="xl" className="py-8">
        <ImmigrationAnswerPanel caseId={primaryCaseId} />
      </Container>
    </AppShell>
  );
};
