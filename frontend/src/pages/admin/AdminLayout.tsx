import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { AdminNotificationBadge } from '../../components/admin/AdminNotificationBadge';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export const AdminLayout: React.FC<Props> = ({ title, subtitle, children }) => {
  const location = useLocation();
  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  return (
    <AppShell title={title} subtitle={subtitle}>
      <div className="mb-6 flex flex-wrap gap-2 border-b border-[#e2e8f0] pb-4">
        <Link
          to={buildRoute('adminConsole')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminConsole.path)
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Dashboard
        </Link>
        <Link
          to={buildRoute('adminCompanies')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminCompanies.path)
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Companies
        </Link>
        <Link
          to={buildRoute('adminResearch')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminResearch.path)
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Research
        </Link>
        <Link
          to={buildRoute('adminUsers')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminUsers.path)
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Users
        </Link>
        <Link
          to={buildRoute('adminRelocations')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminRelocations.path)
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Relocations
        </Link>
        <Link
          to={buildRoute('adminSupport')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminSupport.path)
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Support
        </Link>
        <Link
          to={buildRoute('adminSuppliers')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminSuppliers.path) || isActive('/admin/suppliers/')
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Suppliers
        </Link>
        <Link
          to={buildRoute('adminResources')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminResources.path) ||
            isActive('/admin/resources/') ||
            isActive('/admin/events')
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Resources CMS
        </Link>
        <Link
          to={buildRoute('adminStagingDashboard')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminStagingDashboard.path) || isActive('/admin/staging/')
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Staging
        </Link>
        <Link
          to={buildRoute('adminFreshness')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminFreshness.path) || isActive('/admin/freshness') || isActive('/admin/crawl')
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Freshness
        </Link>
        <Link
          to={buildRoute('adminReviewQueue')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminReviewQueue.path) || isActive('/admin/review-queue')
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Review Queue
        </Link>
        <Link
          to={buildRoute('adminOpsSla')}
          className={`px-3 py-1 rounded-full border text-sm ${
            isActive('/admin/ops')
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Ops
        </Link>
        <Link
          to={buildRoute('adminNotifications')}
          className={`flex items-center gap-1 px-3 py-1 rounded-full border text-sm ${
            isActive(ROUTE_DEFS.adminNotifications.path) || isActive('/admin/notifications/')
              ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
              : 'border-transparent hover:text-[#0b2b43]'
          }`}
        >
          Notifications
          <span className="flex shrink-0">
            <AdminNotificationBadge />
          </span>
        </Link>
      </div>
      {children}
    </AppShell>
  );
};
