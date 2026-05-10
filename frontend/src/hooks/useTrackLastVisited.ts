/**
 * useTrackLastVisited — record the current route as the employee's
 * last-visited position for an assignment, so re-entering from the
 * dashboard returns them here instead of step 1.
 *
 * Call inside any page that's part of the active relocation flow:
 *
 *     useTrackLastVisited(assignmentId);  // tracks current location
 *     useTrackLastVisited(assignmentId, '/services/questions?assignment=…');
 *
 * The second form is for cross-tree routes (e.g. /services/* lives outside
 * /employee/* but is still part of the flow).
 */
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { setLastVisited } from '../utils/employeeCaseProgress';

export function useTrackLastVisited(
  assignmentId: string | null | undefined,
  explicitRoute?: string,
): void {
  const location = useLocation();
  useEffect(() => {
    if (!assignmentId) return;
    const route = explicitRoute || `${location.pathname}${location.search}`;
    setLastVisited(assignmentId, route);
  }, [assignmentId, explicitRoute, location.pathname, location.search]);
}
