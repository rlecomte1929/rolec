import React, { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { addBreadcrumb } from '../lib/errorTracking';
import { trackPageView } from '../lib/analytics';

/**
 * Logs each navigation event to the error tracking breadcrumb buffer
 * and fires a structured page_view analytics event.
 * Place inside <BrowserRouter> or <RouterProvider>.
 */
export const NavigationLogger: React.FC = () => {
  const location = useLocation();
  const isFirst = useRef(true);

  useEffect(() => {
    // Track page view on first mount too (initial page load)
    trackPageView(location.pathname);

    if (isFirst.current) {
      isFirst.current = false;
      return;
    }
    addBreadcrumb({ type: 'navigation', message: location.pathname });
  }, [location.pathname]);

  return null;
};
