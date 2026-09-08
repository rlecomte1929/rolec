/**
 * HrPolicyBuilder — page shell for the HR Policy Builder wizard (AIQ-37-B).
 * Renders inside AppShell; all state is managed by PolicyBuilderWizard internally.
 */
import React from 'react';
import { AppShell } from '../components/AppShell';
import { PolicyBuilderWizard } from '../features/policy-builder/PolicyBuilderWizard';

export const HrPolicyBuilder: React.FC = () => (
  <AppShell>
    <PolicyBuilderWizard />
  </AppShell>
);
