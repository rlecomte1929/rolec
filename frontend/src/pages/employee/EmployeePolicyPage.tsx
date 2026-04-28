import React from 'react';
import { AppShell } from '../../components/AppShell';
import { Container } from '../../components/antigravity';
import { EmployeePolicyView } from '../../features/policy/EmployeePolicyView';

/**
 * Employee read-only view of the published Compensation & Allowance matrix.
 * Route: /employee/policy. Body lives in EmployeePolicyView so the same
 * component can render under the /hr/policy dispatcher when an EMPLOYEE
 * lands on that route.
 */
export const EmployeePolicyPage: React.FC = () => (
  <AppShell title="Compensation & allowance" subtitle="Approved policy for your assignment">
    <Container maxWidth="xl" className="py-8">
      <EmployeePolicyView />
    </Container>
  </AppShell>
);
