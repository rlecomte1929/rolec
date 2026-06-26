/**
 * ServicesLegacyRedirect (AIQ-1249a)
 *
 * Wraps the legacy /services/* routes. Once the employee's case unambiguously
 * resolves, it forwards to the case-id-native URL (/employee/case/:caseId/...)
 * — mirroring the existing providers → services redirect. While the assignment
 * overview is loading, while the case is ambiguous (multi-case picker), or for
 * users with no resolvable case (e.g. HR), it renders the legacy component so
 * nothing breaks and existing ?assignment= deep links keep working.
 */
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useServicesScope } from './useServicesScope';
import { servicesStepPath, type ServicesStep } from './servicesRoutes';

interface ServicesLegacyRedirectProps {
  step: ServicesStep;
  children: React.ReactElement;
}

export const ServicesLegacyRedirect: React.FC<ServicesLegacyRedirectProps> = ({ step, children }) => {
  const { caseId, needsPicker, isLoading } = useServicesScope();
  const location = useLocation();

  if (!isLoading && !needsPicker && caseId) {
    return (
      <Navigate
        to={{ pathname: servicesStepPath(step, { caseId }), search: location.search }}
        replace
      />
    );
  }
  return children;
};
