import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { buildRoute, ROUTE_DEFS, type RouteKey } from '../../../navigation/routes';

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Optional content rendered to the right of the page title (selectors, actions). */
  headerRight?: React.ReactNode;
}

/**
 * Shared Ops-section chrome. Renders the page header + a tab strip with six
 * tabs: Dashboard / SLA / Queue / Reviewers / Destinations / Alerts. Sidebar's
 * "Ops analytics" link points to /admin/ops which lands on the Dashboard tab.
 */
export const AdminOpsLayout: React.FC<Props> = ({ title, subtitle, children, headerRight }) => {
  const location = useLocation();

  // Dashboard tab needs strict match (otherwise it matches all /admin/ops/* sub-routes).
  const isDashboard = location.pathname === ROUTE_DEFS.adminOps.path;
  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  const tabs: Array<{ key: RouteKey; label: string; active: boolean }> = [
    { key: 'adminOps', label: 'Dashboard', active: isDashboard },
    { key: 'adminOpsSla', label: 'SLA', active: !isDashboard && isActive(ROUTE_DEFS.adminOpsSla.path) },
    { key: 'adminOpsQueue', label: 'Queue', active: isActive(ROUTE_DEFS.adminOpsQueue.path) },
    { key: 'adminOpsReviewers', label: 'Reviewers', active: isActive(ROUTE_DEFS.adminOpsReviewers.path) },
    { key: 'adminOpsDestinations', label: 'Destinations', active: isActive(ROUTE_DEFS.adminOpsDestinations.path) },
    { key: 'adminOpsNotifications', label: 'Alerts', active: isActive(ROUTE_DEFS.adminOpsNotifications.path) },
  ];

  return (
    <AdminLayout title={title} subtitle={subtitle} headerRight={headerRight}>
      <div className="mb-5 flex flex-wrap items-center gap-1.5 border-b border-slate-200 pb-3">
        {tabs.map((t) => (
          <Link
            key={t.key}
            to={buildRoute(t.key)}
            className={
              t.active
                ? 'rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white shadow-sm'
                : 'rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50'
            }
          >
            {t.label}
          </Link>
        ))}
      </div>
      {children}
    </AdminLayout>
  );
};
