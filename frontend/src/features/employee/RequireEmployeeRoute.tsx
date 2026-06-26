import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getAuthItem } from '../../utils/demo';

interface RequireEmployeeRouteProps {
  children: React.ReactNode;
  /** When true, HR users are also allowed through (e.g. HR viewing employee checklist). */
  allowHR?: boolean;
}

/**
 * Wraps employee-only routes. HR users are redirected to /hr/dashboard,
 * admin users are allowed through, unauthenticated users are sent to /.
 *
 * This fixes B15: HR navigating to /employee/* used to see an empty employee
 * portal instead of being redirected back to their own dashboard.
 *
 * Pass allowHR={true} to permit HR on specific cross-role pages (e.g. MVG-6B checklist).
 *
 * SECURITY (SEC-FE-4): this guard is a COSMETIC UX hint only. `relopass_role` is read
 * from localStorage, which is user-editable in devtools, so it must NEVER be the access
 * boundary. The real control is server-side: every privileged API independently enforces
 * role + company-scope from the session token (see docs/security/SEC-FE-4_authz_coverage.md).
 * The cached role is derived from the server login response (useAuth.ts → setSession).
 */
export const RequireEmployeeRoute: React.FC<RequireEmployeeRouteProps> = ({ children, allowHR = false }) => {
  const role = (getAuthItem('relopass_role') || '').toUpperCase();
  const location = useLocation();

  if (role === 'ADMIN') {
    // Admins can view employee-facing pages for support/debug purposes.
    return <>{children}</>;
  }

  if (role === 'HR' && allowHR) {
    // Explicitly opted-in HR access (e.g. HR reviewing employee immigration checklist).
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
