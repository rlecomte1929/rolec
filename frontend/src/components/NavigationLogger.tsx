import React, { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { addBreadcrumb } from '../lib/errorTracking';

/**
 * Logs each navigation event to the error tracking breadcrumb buffer.
 * Place inside <BrowserRouter> or <RouterProvider>.
 */
export const NavigationLogger: React.FC = () => {
  const location = useLocation();
  const isFirst = useRef(true);

  useEffect(() => {
    if (isFirst.current) {
      isFirst.current = false;
      return; // skip initial mount — not a navigation event
    }
    addBreadcrumb({ type: 'navigation', message: location.pathname });
  }, [location.pathname]);

  return null;
};
