/**
 * [AIQ-1285/H-05] Back-compat redirect from the legacy path-less /services/* routes
 * to the case-scoped /employee/case/:caseId/services/* equivalents.
 *
 * The case id is the assignment id, resolved from the legacy ?assignment= query or
 * the stored employee preference. Non-assignment query params are preserved. When no
 * case can be resolved, we send the employee to the dashboard to pick one. The
 * destination page re-resolves + guards the case, so trusting the query here is safe.
 */
import { Navigate, useLocation } from 'react-router-dom';
import { buildRoute, ROUTE_DEFS, type RouteKey } from '../../navigation/routes';
import {
  parseAssignmentSearchParam,
  getPreferredEmployeeAssignmentId,
} from '../../utils/employeeAssignmentScope';

export function LegacyServicesRedirect({ to }: { to: RouteKey }) {
  const location = useLocation();
  const caseId = parseAssignmentSearchParam(location.search) || getPreferredEmployeeAssignmentId();

  if (!caseId) {
    return <Navigate to={ROUTE_DEFS.employeeDashboard.path} replace />;
  }

  const params = new URLSearchParams(location.search);
  params.delete('assignment'); // now carried in the path segment
  const qs = params.toString();
  const target = buildRoute(to, { caseId }) + (qs ? `?${qs}` : '');
  return <Navigate to={target} replace />;
}
