/**
 * Employee relocation plan — phased guided experience (GET /api/relocation-plans/{id}/view).
 */
import React from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { EmployeeRelocationPhasedPlan } from '../../features/relocation-plan-employee/EmployeeRelocationPhasedPlan';
import { useTrackLastVisited } from '../../hooks/useTrackLastVisited';

export const EmployeeRelocationPlanPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const routeCaseId = caseId;

  // Track this as the user's last position so re-entering from the
  // dashboard returns them to the plan instead of the case summary.
  useTrackLastVisited(routeCaseId || null);

  return (
    <AppShell>
      {routeCaseId ? (
        <EmployeeRelocationPhasedPlan routeCaseId={routeCaseId} />
      ) : (
        <p className="text-sm text-[#64748b]">Select an assignment from your dashboard to view your plan.</p>
      )}
    </AppShell>
  );
};
