import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';
import { getAdminNotificationCounts, type AdminNotificationCounts } from '../../api/adminCatalog';

const SHOW_RESOURCES_NAV = true;

interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

const navLinkClass = (active: boolean) =>
  `px-3 py-1 rounded-full border text-sm ${
    active ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]' : 'border-transparent hover:text-[#0b2b43]'
  }`;

export const AdminLayout: React.FC<Props> = ({ title, subtitle, children }) => {
  const location = useLocation();
  const isActive = (path: string, exact?: boolean) =>
    exact ? location.pathname === path : location.pathname === path || location.pathname.startsWith(`${path}/`);

  // Phase 2 notifications: poll admin notification counts so the catalog queue
  // tab gets a red badge when HRs have requested destinations the admin hasn't
  // approved yet.
  const [adminNotif, setAdminNotif] = useState<AdminNotificationCounts | null>(null);
  useEffect(() => {
    let cancelled = false;
    const fetchOnce = () => {
      void getAdminNotificationCounts()
        .then((c) => {
          if (!cancelled) setAdminNotif(c);
        })
        .catch(() => {});
    };
    fetchOnce();
    const id = window.setInterval(fetchOnce, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);
  const pendingTickets = adminNotif?.pending_tickets ?? 0;

  const navItems: { to: string; label: string; path?: string; badge?: number }[] = [
    { to: buildRoute('adminOverview'), label: 'Dashboard', path: ROUTE_DEFS.adminOverview.path },
    { to: buildRoute('adminCompanies'), label: 'Companies', path: ROUTE_DEFS.adminCompanies.path },
    { to: buildRoute('adminPeople'), label: 'People', path: ROUTE_DEFS.adminPeople.path },
    { to: buildRoute('adminAssignments'), label: 'Assignments', path: ROUTE_DEFS.adminAssignments.path },
    { to: buildRoute('adminPolicies'), label: 'Policy Workspace', path: ROUTE_DEFS.adminPolicies.path },
    // "Compensation & Allowance" nav item retired — the structured editor now
    // lives inside the Policy Workspace row drawers (one editor, one source
    // of truth). /admin/policy-config route removed entirely.
    { to: buildRoute('adminSuppliers'), label: 'Suppliers', path: ROUTE_DEFS.adminSuppliers.path },
    { to: buildRoute('adminProspects'), label: 'Prospects', path: ROUTE_DEFS.adminProspects.path },
    {
      to: buildRoute('adminCatalogQueue'),
      label: 'Catalog Queue',
      path: ROUTE_DEFS.adminCatalogQueue.path,
      badge: pendingTickets,
    },
    { to: buildRoute('adminMessages'), label: 'Messages', path: ROUTE_DEFS.adminMessages.path },
    { to: buildRoute('adminErrors'), label: 'Errors', path: ROUTE_DEFS.adminErrors.path },
    { to: buildRoute('adminFeedback'), label: 'Feedback', path: ROUTE_DEFS.adminFeedback.path },
  ];
  if (SHOW_RESOURCES_NAV) {
    navItems.push({ to: buildRoute('adminResources'), label: 'Resources', path: ROUTE_DEFS.adminResources.path });
  }

  return (
    <AppShell>
      <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 mb-6">
        <p className="text-sm text-[#475569]">
          <strong className="text-[#0b2b43]">Admin</strong> is global. Open <strong>Companies</strong> or{' '}
          <strong>Assignments</strong> to work in one company context.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 border-b border-[#e2e8f0] pb-4 mb-4">
        {navItems.map(({ to, label, path, badge }) => {
          const pathToCheck = path ?? to;
          const active =
            (pathToCheck === '/admin' ? isActive('/admin', true) : isActive(pathToCheck)) ||
            (pathToCheck === '/admin/suppliers' && isActive('/admin/suppliers/')) ||
            (pathToCheck === '/admin/resources' && (isActive('/admin/resources/') || isActive('/admin/events')));
          return (
            <Link key={label} to={to} className={`${navLinkClass(active)} inline-flex items-center gap-2`}>
              {label}
              {badge && badge > 0 ? (
                <span
                  className="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-[#dc2626] px-1.5 py-0 text-[11px] font-semibold leading-5 text-white"
                  title={`${badge} pending`}
                >
                  {badge}
                </span>
              ) : null}
            </Link>
          );
        })}
      </div>
      <div>
        {title && (
          <div className="mb-4">
            <h1 className="text-2xl font-semibold text-[#0b2b43]">{title}</h1>
            {subtitle && <p className="text-sm text-[#4b5563] mt-1">{subtitle}</p>}
          </div>
        )}
        {children}
      </div>
    </AppShell>
  );
};
