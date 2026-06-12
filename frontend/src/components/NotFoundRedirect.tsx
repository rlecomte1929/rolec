import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getAuthItem } from '../utils/demo';
import { roleHomePath } from '../navigation/roleHome';

/**
 * Catch-all redirect for unmatched routes. An authenticated user is sent to
 * their role's dashboard (so e.g. an employee opening /hr/assignments lands on
 * /employee/dashboard, not the marketing homepage); anonymous visitors fall
 * back to the public landing — the original catch-all behaviour. (AIQ-980)
 *
 * This only changes WHERE an unmatched URL lands; it does not grant access to
 * any guarded route — the per-route RequireHrRoute / RequireAdminRoute /
 * RequireEmployeeRoute guards still enforce authorization.
 */
export const NotFoundRedirect: React.FC = () => {
  const role = getAuthItem('relopass_role');
  const location = useLocation();
  return <Navigate to={roleHomePath(role)} state={{ from: location }} replace />;
};
