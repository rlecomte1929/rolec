import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getAuthItem } from '../../utils/demo';

interface RequireEmployeeRouteProps {
  children: React.ReactNode;
}

/**
 * Wraps employee-only routes. HR users are redirected to /hr/dashboard,
 * admin users are allowed through, unauthenticated users are sent to /.
 *
 * This fixes B15: HR navigating to /employee/* used to see an empty employee
 * portal instead of being redirected back to their own dashboard.
 */
export const RequireEmployeeRoute: React.FC<RequireEmployeeRouteProps> = ({ children }) => {
  const role = (getAuthItem('relopass_role') || '').toUpperCase();
  const location = useLocation();

  if (role === 'ADMIN') {
    // Admins can view employee-facing pages for support/debug purposes.
    return <>{children}</>;
  }

  if (role !== 'EMPLOYEE') {
    // HR and any unrecognised role → redirect to their own landing page.
    const redirectTo =
      role === 'HR' ? '/hr/dashboard' : '/';
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
