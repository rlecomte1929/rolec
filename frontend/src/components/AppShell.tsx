import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Container } from './antigravity';
import { clearAuthItems, getAuthItem } from '../utils/demo';
import { getNavigationError } from '../navigation/safeNavigate';
import { buildRoute, ROUTE_DEFS } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';

const logoUrl = '/relopass-logo.png?v=1';

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
}

export const AppShell: React.FC<AppShellProps> = ({ children, title, subtitle }) => {
  const name = getAuthItem('relopass_name');
  const role = getAuthItem('relopass_role');
  const identity = name || getAuthItem('relopass_email') || getAuthItem('relopass_username');
  const location = useLocation();
  const [navError, setNavError] = useState<string | null>(getNavigationError());
  const isHrRole = role === 'HR';
  const lastAssignmentId = localStorage.getItem('relopass_last_assignment_id');

  const isActiveRoute = (path: string) => {
    if (path.includes('/:')) {
      const base = path.split('/:')[0];
      return location.pathname.startsWith(base);
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const complianceRoute = lastAssignmentId
    ? `${buildRoute('hrComplianceIndex')}?caseId=${lastAssignmentId}`
    : buildRoute('hrComplianceIndex');
  const policyRoute = lastAssignmentId
    ? `${buildRoute('hrPolicy')}?caseId=${lastAssignmentId}`
    : buildRoute('hrPolicy');

  useRegisterNav('AppShell', [
    { label: 'Employee view', routeKey: 'employeeJourney' },
    { label: 'HR view', routeKey: 'hrDashboard' },
  ]);

  useEffect(() => {
    const handler = (event: Event) => {
      const custom = event as CustomEvent<string>;
      setNavError(custom.detail || null);
    };
    window.addEventListener('nav-error', handler as EventListener);
    return () => window.removeEventListener('nav-error', handler as EventListener);
  }, []);

  return (
    <div className="min-h-screen bg-[#f5f7fa] text-[#1f2937] flex flex-col">
      <header className="border-b border-[#e2e8f0] bg-white">
        <Container maxWidth="xl" className="py-4 flex items-center justify-between">
          <Link to={buildRoute('landing')} className="flex items-center gap-3">
            <img
              src={logoUrl}
              alt="ReloPass logo"
              className="h-16 w-16 rounded-xl object-contain"
            />
            <div>
              <div className="text-lg font-semibold text-[#0b2b43]">ReloPass</div>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                clearAuthItems();
                window.location.href = buildRoute('landing');
              }}
              className="text-xs text-[#4b5563] hover:text-[#0b2b43] border border-[#e2e8f0] px-3 py-1 rounded-full"
            >
              Switch user
            </button>
            <div className="text-right text-sm text-slate-600">
              {identity && <div className="font-medium text-[#0f172a]">{identity}</div>}
              {role && <div className="uppercase tracking-wide text-xs text-[#6b7280]">{role}</div>}
            </div>
          </div>
        </Container>
        {isHrRole && (
          <div className="border-t border-[#e2e8f0]">
            <Container maxWidth="xl" className="py-3 flex items-center justify-between gap-6">
              <div className="flex flex-wrap items-center gap-4">
                <input
                  placeholder="Search cases..."
                  className="w-56 rounded-full border border-[#e2e8f0] bg-white px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
                />
                <nav className="flex flex-wrap items-center gap-2 text-sm text-[#6b7280]">
                  <Link
                    to={buildRoute('hrDashboard')}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrDashboard.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    HR Dashboard
                  </Link>
                  <Link
                    to={buildRoute('hrEmployeeDashboard')}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrEmployeeDashboard.path) ||
                      isActiveRoute(ROUTE_DEFS.hrAssignmentReview.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    Employee Dashboard
                  </Link>
                  <Link
                    to={complianceRoute}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrComplianceIndex.path) || isActiveRoute(ROUTE_DEFS.hrCompliance.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    Compliance Check
                  </Link>
                  <Link
                    to={policyRoute}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrPolicy.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    HR Policy
                  </Link>
                  <Link
                    to={buildRoute('hrMessages')}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrMessages.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    Messages
                  </Link>
                  <Link
                    to={buildRoute('hrResources')}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrResources.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    Resources
                  </Link>
                </nav>
              </div>
              <div className="flex items-center gap-3">
                <button className="h-9 w-9 rounded-full border border-[#e2e8f0] flex items-center justify-center text-[#64748b] hover:text-[#0b2b43]">
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
                    <path d="M18 8a6 6 0 10-12 0c0 7-3 7-3 7h18s-3 0-3-7Z" />
                    <path d="M13.73 21a2 2 0 01-3.46 0" />
                  </svg>
                </button>
                <button className="h-9 w-9 rounded-full bg-[#0b2b43] text-white text-xs font-semibold">
                  {identity ? identity.slice(0, 2).toUpperCase() : 'HR'}
                </button>
              </div>
            </Container>
          </div>
        )}
      </header>

      {navError && (
        <div className="bg-[#fff5f5] border-b border-[#fbd5d5] text-[#7a2a2a] text-sm">
          <Container maxWidth="xl" className="py-2">
            Navigation blocked: {navError}
          </Container>
        </div>
      )}

      <main className="flex-1">
        <Container maxWidth="xl" className="py-8">
          {title && (
            <div className="mb-6">
              <h1 className="text-2xl font-semibold text-[#0b2b43]">{title}</h1>
              {subtitle && <p className="text-sm text-[#4b5563] mt-1">{subtitle}</p>}
            </div>
          )}
          {children}
        </Container>
      </main>

      <footer className="border-t border-[#e2e8f0] bg-white">
        <Container maxWidth="xl" className="py-4 text-xs text-[#6b7280] flex items-center justify-between">
          <span>Informational guidance only. ReloPass does not provide legal advice.</span>
          <div className="flex items-center gap-3">
          </div>
        </Container>
      </footer>
    </div>
  );
};
