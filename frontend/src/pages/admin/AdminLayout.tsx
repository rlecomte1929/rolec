import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
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
    { to: buildRoute('adminPolicies'), label: 'Policy Workspace', path: ROUTE_DEFS.adminPolicies.path },
    {
      to: buildRoute('adminPolicyConfig'),
      label: 'Compensation & Allowance',
      path: ROUTE_DEFS.adminPolicyConfig.path,
    },
    { to: buildRoute('adminSuppliers'), label: 'Suppliers', path: ROUTE_DEFS.adminSuppliers.path },
    { to: buildRoute('adminMessages'), label: 'Messages', path: ROUTE_DEFS.adminMessages.path },
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
        {navItems.map(({ to, label, path }) => {
          const pathToCheck = path ?? to;
          const active =
            (pathToCheck === '/admin' ? isActive('/admin', true) : isActive(pathToCheck)) ||
            (pathToCheck === '/admin/suppliers' && isActive('/admin/suppliers/')) ||
            (pathToCheck === '/admin/resources' && (isActive('/admin/resources/') || isActive('/admin/events')));
          return (
            <Link key={label} to={to} className={navLinkClass(active)}>
              {label}
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
