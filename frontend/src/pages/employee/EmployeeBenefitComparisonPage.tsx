import React, { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { Card, Container } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
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
 */
export const EmployeeBenefitComparisonPage: React.FC = () => {
  const { assignmentId, isLoading: assignmentLoading, linkedCount } = useEmployeeAssignment();

  const [comp, setComp] = useState<PolicyServiceComparisonResponse | null>(null);
  const [policy, setPolicy] = useState<PolicyFooter | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!assignmentId) {
      setComp(null);
      setPolicy(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      employeeAPI.getPolicyServiceComparison(assignmentId),
      employeeAPI.getServicesPolicyContext(assignmentId),
    ])
      .then(([compRes, ctxRes]) => {
        if (cancelled) return;
        if (compRes.status === 'fulfilled') {
          setComp(compRes.value);
        } else {
          setComp(null);
          setError('We could not load your benefit comparison right now. Please try again shortly.');
        }
        if (ctxRes.status === 'fulfilled' && ctxRes.value.policy_surface) {
          const ps = ctxRes.value.policy_surface as PolicyFooter & {
            expiry_date?: string | null;
            company_name?: string | null;
            effective_date?: string | null;
          };
          setPolicy({
            companyName: ps.company_name ?? null,
            version: ps.version ?? null,
            effectiveDate: ps.effective_date ?? null,
            expiryDate: ps.expiry_date ?? null,
          });
        } else {
          setPolicy(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  const rows = useMemo(() => comp?.effective_service_comparison ?? [], [comp]);
  const caseId = comp?.case_id ?? null;

  return (
    <AppShell
      title="Benefit comparison"
      subtitle="What's covered, what you'd owe, and what you can request"
    >
      <Container maxWidth="xl" className="py-8">
        {!assignmentLoading && !assignmentId && linkedCount === 0 ? (
          <Card padding="lg" className="border-[#e2e8f0]">
            <p className="mb-1 text-sm font-medium text-[#0b2b43]">No company linked yet</p>
            <p className="text-sm text-[#64748b]">
              Your benefit comparison appears here automatically once HR links your account to an
              assignment. No action is needed on your part.
            </p>
          </Card>
        ) : loading ? (
          <Card padding="lg" className="border-[#e2e8f0]">
            <p className="text-sm text-[#64748b]">Loading your benefit comparison…</p>
          </Card>
        ) : error ? (
          <Card padding="lg" className="border-slate-200 bg-slate-50/50">
            <p className="text-sm text-slate-700">{error}</p>
          </Card>
        ) : (
          <BenefitComparisonDashboard rows={rows} caseId={caseId} policy={policy} />
        )}
      </Container>
    </AppShell>
  );
};

export default EmployeeBenefitComparisonPage;
