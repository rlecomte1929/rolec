import React, { useMemo } from 'react';
import { AppShell } from '../../components/AppShell';
import { Button, Card, Container } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useResilientQuery } from '../../hooks/useResilientQuery';
import {
  BenefitComparisonDashboard,
  type PolicyFooter,
} from '../../features/policy/BenefitComparisonDashboard';
import type { PolicyServiceComparisonResponse } from '../../types';

/**
 * Employee Benefit Comparison dashboard page (P3-2 / AIQ-237).
 * Route: /employee/benefits.
 *
 * Fetches the honest comparison engine output + the resolved policy surface
 * (for the footer / expiry), then hands both to the presentational dashboard.
 *
 * AIQ-655: data fetch goes through useResilientQuery so the page renders
 * exactly one of skeleton / offline / error (with Retry) / content, with a
 * stale response after navigation never landing.
 */
interface ComparisonData {
  comp: PolicyServiceComparisonResponse | null;
  policy: PolicyFooter | null;
}

export const EmployeeBenefitComparisonPage: React.FC = () => {
  const { assignmentId, isLoading: assignmentLoading, linkedCount } = useEmployeeAssignment();

  const { data, error, loading, isOffline, retry } = useResilientQuery<ComparisonData>(
    async () => {
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
    [assignmentId],
  );

  const comp = data?.comp ?? null;
  const policy = data?.policy ?? null;
  const rows = useMemo(() => comp?.effective_service_comparison ?? [], [comp]);
  const caseId = comp?.case_id ?? null;

  let body: React.ReactNode;
  if (!assignmentLoading && !assignmentId && linkedCount === 0) {
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
  } else {
    body = <BenefitComparisonDashboard rows={rows} caseId={caseId} policy={policy} />;
  }

  return (
    <AppShell
      title="Benefit comparison"
      subtitle="What's covered, what you'd owe, and what you can request"
    >
      <Container maxWidth="xl" className="py-8">
        {body}
      </Container>
    </AppShell>
  );
};

export default EmployeeBenefitComparisonPage;
