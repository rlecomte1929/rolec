import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Container } from '../components/antigravity';
import { PolicyConfigPage } from '../features/policy-config/PolicyConfigPage';
import { PolicyConfigRouteErrorBoundary } from '../features/policy-config/PolicyConfigRouteErrorBoundary';

/**
 * HR (and Admin via ?adminCompanyId=) — structured Compensation & Allowance matrix.
 */
export const HrPolicyConfigPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const adminCompanyId = searchParams.get('adminCompanyId');

  return (
    <AppShell title="Compensation & Allowance" subtitle="Policy configuration">
      <Container maxWidth="xl" className="py-8">
        <PolicyConfigRouteErrorBoundary>
          <PolicyConfigPage mode="hr" hrCompanyIdOverride={adminCompanyId} />
        </PolicyConfigRouteErrorBoundary>
      </Container>
    </AppShell>
  );
};
