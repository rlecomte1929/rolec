import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AppShell } from '../../components/AppShell';
import { Button, Card, Container } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { resolveOverviewState } from '../../features/employee-journey/overviewResolution';
import { useIsOffline } from '../../hooks/useOnlineStatus';
import { isIntakeComplete } from '../../features/employee-journey/caseStage';
import { PolicyAssistantFab } from '../../features/policy/PolicyAssistantFab';
import { PolicyAssistantDockedShell } from '../../features/policy/PolicyAssistantDockedShell';
import { EmployeePolicyAssistantPanel } from '../../features/policy/EmployeePolicyAssistantPanel';
import {
  BenefitComparisonDashboard,
  type PolicyFooter,
} from '../../features/policy/BenefitComparisonDashboard';
import { BudgetSummaryTable } from '../../features/services/BudgetSummaryTable';
import type { PolicyServiceComparisonResponse } from '../../types';

/**
 * Employee Benefit Comparison dashboard page (P3-2 / AIQ-237).
 * Route: /employee/benefits.
 *
 * Fetches the honest comparison engine output + the resolved policy surface
 * (for the footer / expiry), then hands both to the presentational dashboard.
 *
 * AIQ-655 / RX-3g: data fetch goes through TanStack Query (useQuery) + useIsOffline
 * so the page renders exactly one of skeleton / offline / error (with Retry) /
 * content; query keying prevents a stale response after navigation from landing.
 */
interface ComparisonData {
  comp: PolicyServiceComparisonResponse | null;
  policy: PolicyFooter | null;
}

export const EmployeeBenefitComparisonPage: React.FC = () => {
  const {
    assignmentId, isLoading: assignmentLoading, linkedCount, pendingCount,
    overviewError, overviewDegraded, linkedSummaries,
  } =
    useEmployeeAssignment();
  const activeRow = linkedSummaries.find((r) => r.assignment_id === assignmentId);
  const [assistantOpen, setAssistantOpen] = useState(false);

  const comparisonQuery = useQuery({
    queryKey: ['employee', 'benefit-comparison', assignmentId],
    // Auto-reload when the connection returns (preserves the retired resilient behavior).
    refetchOnReconnect: true,
    queryFn: async (): Promise<ComparisonData> => {
      if (!assignmentId) return { comp: null, policy: null };
      const [compRes, ctxRes] = await Promise.allSettled([
        employeeAPI.getPolicyServiceComparison(assignmentId),
        employeeAPI.getServicesPolicyContext(assignmentId),
      ]);
      // The comparison is the load-bearing call; a missing policy surface only
      // drops the footer, so only the comparison failing is a page error.
      if (compRes.status === 'rejected') {
        throw new Error(
          'We could not load your benefit comparison right now. Please try again shortly.',
        );
      }
      let policy: PolicyFooter | null = null;
      if (ctxRes.status === 'fulfilled' && ctxRes.value.policy_surface) {
        const ps = ctxRes.value.policy_surface as PolicyFooter & {
          expiry_date?: string | null;
          company_name?: string | null;
          effective_date?: string | null;
        };
        policy = {
          companyName: ps.company_name ?? null,
          version: ps.version ?? null,
          effectiveDate: ps.effective_date ?? null,
          expiryDate: ps.expiry_date ?? null,
        };
      }
      return { comp: compRes.value, policy };
    },
  });

  const data: ComparisonData | null = comparisonQuery.data ?? null;
  const loading = comparisonQuery.isLoading;
  const error = comparisonQuery.error;
  const isOffline = useIsOffline();
  const retry = () => {
    void comparisonQuery.refetch();
  };

  const comp = data?.comp ?? null;
  const policy = data?.policy ?? null;
  const rows = useMemo(() => comp?.effective_service_comparison ?? [], [comp]);
  const caseId = comp?.case_id ?? null;

  let body: React.ReactNode;
  // AIQ-2285/T8: only claim "not linked" once the overview actually resolved.
  const { unresolved: overviewUnresolved } = resolveOverviewState({
    overviewError, overviewDegraded, linkedCount, pendingCount,
  });
  if (!assignmentLoading && overviewUnresolved && !assignmentId) {
    body = (
      <Card padding="lg" className="border-[#e2e8f0]">
        <p className="mb-1 text-sm font-medium text-[#0b2b43]">We couldn&apos;t load your benefits</p>
        <p className="text-sm text-[#64748b]">This is usually temporary. Refresh the page to try again.</p>
      </Card>
    );
  } else if (!assignmentLoading && !assignmentId && linkedCount === 0) {
    body = (
      <Card padding="lg" className="border-[#e2e8f0]">
        <p className="mb-1 text-sm font-medium text-[#0b2b43]">No company linked yet</p>
        <p className="text-sm text-[#64748b]">
          Your benefit comparison appears here automatically once HR links your account to an
          assignment. No action is needed on your part.
        </p>
      </Card>
    );
  } else if (assignmentLoading || loading) {
    body = (
      <Card padding="lg" className="border-[#e2e8f0]">
        <p className="text-sm text-[#64748b]">Loading your benefit comparison…</p>
      </Card>
    );
  } else if (isOffline) {
    body = (
      <Card padding="lg" className="border-slate-200 bg-slate-50/50">
        <p className="mb-3 text-sm text-slate-700">
          You appear to be offline. Your benefit comparison will load once you reconnect.
        </p>
        <Button variant="outline" onClick={retry}>
          Retry
        </Button>
      </Card>
    );
  } else if (error) {
    body = (
      <Card padding="lg" className="border-slate-200 bg-slate-50/50">
        <p className="mb-3 text-sm text-slate-700">{error.message}</p>
        <Button variant="primary" onClick={retry}>
          Retry
        </Button>
      </Card>
    );
  } else if (comp && comp.resolved_policy === null) {
    // No published policy → friendly employee-facing onboarding nudge (not a blank
    // page or raw "no policy" error). HR is prompted to publish on their side.
    body = (
      <Card padding="lg" className="border-[#e2e8f0]">
        <p className="mb-1 text-sm font-medium text-[#0b2b43]">No benefits policy published yet</p>
        <p className="text-sm text-[#64748b]">
          Your HR team hasn&rsquo;t published a benefits policy yet. Once they do, you&rsquo;ll see which
          services are covered — and what you&rsquo;d owe — right here. No action is needed on your part.
        </p>
      </Card>
    );
  } else if (comp && rows.length === 0) {
    // [AIQ-1253/H-06] Policy resolved but no services matched yet. Show the policy
    // benefit caps table from existing data (BudgetSummaryTable fetches per-case
    // caps independently of service matching), and demote the "no services matched"
    // copy to a note below — so the page is no longer an empty dead end.
    body = (
      <div className="space-y-4">
        {assignmentId && <BudgetSummaryTable caseId={assignmentId} displayCurrency="USD" />}
        <Card padding="lg" className="border-[#e2e8f0]">
          <p className="mb-1 text-sm font-medium text-[#0b2b43]">No services matched yet</p>
          <p className="text-sm text-[#64748b]">
            {isIntakeComplete(activeRow?.status)
              ? "Your benefits policy is published and the caps above apply to your case. We'll show which services are covered and what you'd owe as your policy is matched to services."
              : "Your benefits policy is published and the caps above apply to your case. Complete your intake and we'll match services and show what you'd owe."}
          </p>
        </Card>
      </div>
    );
  } else {
    body = <BenefitComparisonDashboard rows={rows} caseId={caseId} policy={policy} />;
  }

  return (
    <AppShell
      title="Benefit comparison"
      subtitle="What's covered, what you'd owe, and what you can request"
    >
      <PolicyAssistantDockedShell
        open={assistantOpen}
        onOpenChange={setAssistantOpen}
        title="Ask about your policy"
        subtitle="Bounded Q&A on your published policy."
        titleId="employee-benefits-assistant-shell-title"
        assistant={() => (
          <EmployeePolicyAssistantPanel
            assignmentId={assignmentId}
            assignmentLoading={assignmentLoading}
            variant="embedded"
          />
        )}
      >
        <Container maxWidth="xl" className="py-8">
          {body}
        </Container>
      </PolicyAssistantDockedShell>
      <PolicyAssistantFab
        label="Ask about your policy"
        isPanelOpen={assistantOpen}
        onClick={() => setAssistantOpen((v) => !v)}
      />
    </AppShell>
  );
};

export default EmployeeBenefitComparisonPage;
