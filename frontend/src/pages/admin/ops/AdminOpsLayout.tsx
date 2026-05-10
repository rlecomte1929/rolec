import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { buildRoute, ROUTE_DEFS } from '../../../navigation/routes';

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export const AdminOpsLayout: React.FC<Props> = ({ title, subtitle, children }) => {
  const location = useLocation();
  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  return (
    <AdminLayout title={title} subtitle={subtitle}>
      <div className="mb-4 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        <Link
          to={buildRoute('adminOpsSla')}
          className={`rounded-full border px-3 py-1 text-sm ${
            isActive(ROUTE_DEFS.adminOpsSla.path)
              ? 'border-[#0b2b43] bg-[#eef4f8] text-[#0b2b43]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          SLA
        </Link>
        <Link
          to={buildRoute('adminOpsQueue')}
          className={`rounded-full border px-3 py-1 text-sm ${
            isActive(ROUTE_DEFS.adminOpsQueue.path)
              ? 'border-[#0b2b43] bg-[#eef4f8] text-[#0b2b43]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Queue
        </Link>
        <Link
          to={buildRoute('adminOpsReviewers')}
          className={`rounded-full border px-3 py-1 text-sm ${
            isActive(ROUTE_DEFS.adminOpsReviewers.path)
              ? 'border-[#0b2b43] bg-[#eef4f8] text-[#0b2b43]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Reviewers
        </Link>
        <Link
          to={buildRoute('adminOpsDestinations')}
          className={`rounded-full border px-3 py-1 text-sm ${
            isActive(ROUTE_DEFS.adminOpsDestinations.path)
              ? 'border-[#0b2b43] bg-[#eef4f8] text-[#0b2b43]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Destinations
        </Link>
        <Link
          to={buildRoute('adminOpsNotifications')}
          className={`rounded-full border px-3 py-1 text-sm ${
            isActive(ROUTE_DEFS.adminOpsNotifications.path)
              ? 'border-[#0b2b43] bg-[#eef4f8] text-[#0b2b43]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Alerts
        </Link>
      </div>
      {children}
    </AdminLayout>
  );
};
