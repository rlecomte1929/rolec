/**
 * RequireEmployeeRoute  (B15)
 *
 * Wraps /employee/* routes to block HR users from accessing the employee
 * portal.  HR users are redirected to /hr/command-center; unauthenticated
 * users are redirected to the landing page.
 *
 * ADMIN users are allowed through — they can impersonate either side.
 */
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getAuthItem } from '../utils/demo';
import { buildRoute } from '../navigation/routes';

interface RequireEmployeeRouteProps {
  children: React.ReactNode;
}

export const RequireEmployeeRoute: React.FC<RequireEmployeeRouteProps> = ({ children }) => {
  const location = useLocation();
  const role = (getAuthItem('relopass_role') || '').toUpperCase();

  // Not authenticated at all → landing
  if (!role) {
    return <Navigate to={buildRoute('landing')} state={{ from: location }} replace />;
  }

  // HR users are not allowed in the employee portal → redirect to command center
  if (role === 'HR') {
    return <Navigate to={buildRoute('hrCommandCenter')} replace />;
  }

  // EMPLOYEE and ADMIN pass through
  return <>{children}</>;
};
