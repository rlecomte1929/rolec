import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useIsAdmin, getAdminRedirectPath } from './useIsAdmin';

interface RequireAdminRouteProps {
  children: React.ReactNode;
}

/**
 * Wraps admin-only routes. Redirects non-admin users before rendering.
 */
export const RequireAdminRoute: React.FC<RequireAdminRouteProps> = ({ children }) => {
  const isAdmin = useIsAdmin();
  const location = useLocation();

  if (!isAdmin) {
    const redirectTo = getAdminRedirectPath();
    return <Navigate to={redirectTo} state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
