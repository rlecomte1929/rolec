import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { buildRoute, ROUTE_DEFS } from '../../../navigation/routes';

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export const AdminReviewQueueLayout: React.FC<Props> = ({ title, subtitle, children }) => {
  const location = useLocation();
  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  return (
    <AdminLayout title={title} subtitle={subtitle}>
      <div className="mb-4 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        <Link
          to={buildRoute('adminReviewQueue')}
          className={`rounded-full border px-3 py-1 text-sm ${
            (isActive(ROUTE_DEFS.adminReviewQueue.path) && !location.pathname.includes('/workload'))
              ? 'border-[#0b2b43] bg-[#eef4f8] text-[#0b2b43]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Queue
        </Link>
        <Link
          to={buildRoute('adminReviewQueueWorkload')}
          className={`rounded-full border px-3 py-1 text-sm ${
            isActive(ROUTE_DEFS.adminReviewQueueWorkload.path)
              ? 'border-[#0b2b43] bg-[#eef4f8] text-[#0b2b43]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Workload
        </Link>
      </div>
      {children}
    </AdminLayout>
  );
};
