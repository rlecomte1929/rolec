import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
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
      </div>
      {children}
    </AppShell>
  );
};
