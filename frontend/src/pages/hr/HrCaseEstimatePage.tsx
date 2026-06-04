// HrCaseEstimatePage.tsx — HR Estimate Review (AIQ-280 / T1.5).
//
// Route: /hr/cases/:caseId/estimate (HR + ADMIN only).
// Surfaces the same backend data the employee sees on /employee/services/estimate
// but in the policy's *native* currency (HR thinks in policy currency) and adds
// a CTA that links to the global exceptions inbox for raising a cap exception.
//
// Role gating is page-level — there is no shared RequireHrRoute today and we
// stick to the page-local idiom used in InboxV2Page, HrCompanyContext, and
// EmployeeAssignmentContext (see the audit context recon for AIQ-280).

import React from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card } from '../../components/antigravity';
import { BudgetSummaryTable } from '../../features/services/BudgetSummaryTable';
import { ProcessingTimeCard } from '../../features/services/ProcessingTimeCard';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';

export const HrCaseEstimatePage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const role = normalizeStoredRole(getAuthItem('relopass_role'));

  if (role !== 'HR' && role !== 'ADMIN') {
    return <Navigate to="/hr/dashboard" replace />;
  }

  if (!caseId) {
    return <Navigate to="/hr/dashboard" replace />;
  }

  return (
    <AppShell
      section="HR Operations"
      title="Estimate"
      subtitle="Policy caps for this relocation case."
    >
      <BudgetSummaryTable
        caseId={caseId}
        displayCurrency="USD"
        nativeCurrencyForCaps
      />

      <ProcessingTimeCard caseId={caseId} />

      <Card padding="lg" className="mt-6">
        <p className="text-sm font-semibold text-[#0b2b43] mb-1">Need to go over a cap?</p>
        <p className="text-sm text-[#4b5563] mb-3">
          Open an exception request for this case to record the rationale and route it for
          approval. Exceptions are tracked in the policy exceptions inbox.
        </p>
        <Button onClick={() => navigate(buildRoute('hrExceptions'))}>
          Request a policy exception
        </Button>
      </Card>

      <div className="mt-6">
        <Button
          variant="outline"
          onClick={() => navigate(buildRoute('hrCommandCenterCase', { id: caseId }))}
        >
          ← Back to case detail
        </Button>
      </div>
    </AppShell>
  );
};

export default HrCaseEstimatePage;
