/**
 * Employee relocation plan — phased guided experience (GET /api/relocation-plans/{id}/view).
 */
import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { EmployeeRelocationPhasedPlan } from '../../features/relocation-plan-employee/EmployeeRelocationPhasedPlan';
import { useTrackLastVisited } from '../../hooks/useTrackLastVisited';
import { PolicyAssistantFab } from '../../features/policy/PolicyAssistantFab';
import { PolicyAssistantDockedShell } from '../../features/policy/PolicyAssistantDockedShell';
import { EmployeePolicyAssistantPanel } from '../../features/policy/EmployeePolicyAssistantPanel';

export const EmployeeRelocationPlanPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const routeCaseId = caseId;

  // Track this as the user's last position so re-entering from the
  // dashboard returns them to the plan instead of the case summary.
  useTrackLastVisited(routeCaseId || null);

  // Sprint 2: docked shell + trigger-only FAB. The FAB hides on lg+
  // when the panel is open so it doesn't sit on top of the panel; the
  // panel's own close button is the dismissal affordance there. On
  // <lg the panel renders as a bottom sheet and the FAB stays visible
  // behind it for re-entry on close.
  const [assistantOpen, setAssistantOpen] = useState(false);

  return (
    <AppShell>
      <PolicyAssistantDockedShell
        open={assistantOpen}
        onOpenChange={setAssistantOpen}
        title="Ask about your policy"
        subtitle="Bounded Q&A on your published policy."
        titleId="employee-plan-assistant-shell-title"
        assistant={() => (
          <EmployeePolicyAssistantPanel
            assignmentId={routeCaseId}
            assignmentLoading={false}
            variant="embedded"
          />
        )}
      >
        {routeCaseId ? (
          <EmployeeRelocationPhasedPlan routeCaseId={routeCaseId} />
        ) : (
          <p className="text-sm text-[#64748b]">
            Select an assignment from your dashboard to view your plan.
          </p>
        )}
      </PolicyAssistantDockedShell>
      <PolicyAssistantFab
        label="Ask about your policy"
        isPanelOpen={assistantOpen}
        onClick={() => setAssistantOpen((v) => !v)}
      />
    </AppShell>
  );
};
