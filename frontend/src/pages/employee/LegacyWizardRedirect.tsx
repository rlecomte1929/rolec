import React from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';

/**
 * Staged wizard unification (C1). The legacy CaseWizardPage routes
 * (/employee/case/:caseId/wizard[/:step] and /review) now redirect to the single
 * canonical v2 intake (/employee/case/:caseId/intake). The v2 wizard resumes to the
 * last-saved step on hydration, so the legacy per-step URLs need not be preserved.
 * CaseWizardPage stays in the tree (dormant) until v2 is fully validated.
 */
export const LegacyWizardRedirect: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  return (
    <Navigate
      to={caseId ? buildRoute('employeeCaseIntake', { caseId }) : ROUTE_DEFS.employeeIntake.path}
      replace
    />
  );
};
