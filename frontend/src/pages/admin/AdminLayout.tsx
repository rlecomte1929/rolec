import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { AdminNotificationBadge } from '../../components/admin/AdminNotificationBadge';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';

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

  const navItems: { to: string; label: string; path?: string }[] = [
    { to: buildRoute('adminOverview'), label: 'Dashboard', path: ROUTE_DEFS.adminOverview.path },
    { to: buildRoute('adminCompanies'), label: 'Companies', path: ROUTE_DEFS.adminCompanies.path },
    { to: buildRoute('adminPeople'), label: 'People', path: ROUTE_DEFS.adminPeople.path },
    { to: buildRoute('adminAssignments'), label: 'Assignments', path: ROUTE_DEFS.adminAssignments.path },
    { to: buildRoute('adminPolicies'), label: 'Policies', path: ROUTE_DEFS.adminPolicies.path },
    { to: buildRoute('adminSuppliers'), label: 'Suppliers', path: ROUTE_DEFS.adminSuppliers.path },
    { to: buildRoute('adminMessages'), label: 'Messages', path: ROUTE_DEFS.adminMessages.path },
    { to: buildRoute('adminReconciliation'), label: 'Reconciliation', path: ROUTE_DEFS.adminReconciliation.path },
  ];
  if (SHOW_RESOURCES_NAV) {
    navItems.push({ to: buildRoute('adminResources'), label: 'Resources', path: ROUTE_DEFS.adminResources.path });
  }
  navItems.push({
    to: buildRoute('adminNotifications'),
    label: 'Notifications',
    path: ROUTE_DEFS.adminNotifications.path,
  });

  return (
    <AppShell>
      <div className="flex flex-wrap gap-2 border-b border-[#e2e8f0] pb-4 mb-4">
        {navItems.map(({ to, label, path }) => {
          const pathToCheck = path ?? to;
          const active =
            (pathToCheck === '/admin' ? isActive('/admin', true) : isActive(pathToCheck)) ||
            (pathToCheck === '/admin/suppliers' && isActive('/admin/suppliers/')) ||
            (pathToCheck === '/admin/resources' && (isActive('/admin/resources/') || isActive('/admin/events')));
          const isNotifications = label === 'Notifications';
          return (
            <Link key={label} to={to} className={navLinkClass(active)}>
              {isNotifications ? (
                <span className="flex items-center gap-1">
                  {label}
                  <span className="flex shrink-0">
                    <AdminNotificationBadge />
                  </span>
                </span>
              ) : (
                label
              )}
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
