import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Container } from './antigravity';
import { clearAuthItems, getAuthItem } from '../utils/demo';
import { authAPI } from '../api/client';
import { getNavigationError } from '../navigation/safeNavigate';
import { buildRoute, ROUTE_DEFS } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { useAdminContext } from '../features/admin/useAdminContext';
import { adminAPI } from '../api/client';

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
  const isHrRole = role === 'HR' || role === 'ADMIN';
  const isEmployeeRole = role === 'EMPLOYEE' || role === 'ADMIN';
  const { selectedCaseId } = useSelectedCase();
  const { assignmentId } = useEmployeeAssignment();
  const { context: adminContext, refresh: refreshAdminContext } = useAdminContext();

  const isActiveRoute = (path: string) => {
    if (path.includes('/:')) {
      const base = path.split('/:')[0];
      return location.pathname.startsWith(base);
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const complianceRoute = selectedCaseId
    ? `${buildRoute('hrComplianceIndex')}?caseId=${selectedCaseId}`
    : buildRoute('hrComplianceIndex');
  const policyRoute = selectedCaseId
    ? `${buildRoute('hrPolicy')}?caseId=${selectedCaseId}`
    : buildRoute('hrPolicy');
  const messagesRoute = selectedCaseId
    ? `${buildRoute('hrMessages')}?caseId=${selectedCaseId}`
    : buildRoute('hrMessages');

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
          </Link>
          <div className="flex items-center gap-4">
            <button
              onClick={async () => {
                await authAPI.logout();
                window.location.replace(buildRoute('landing'));
              }}
              className="text-xs text-[#94a3b8] hover:text-[#0b2b43]"
            >
              Logout
            </button>
            <div className="text-right text-sm text-slate-600">
              {identity && (
                <Link
                  to={role === 'EMPLOYEE' ? buildRoute('employeeJourney') : role === 'HR' || role === 'ADMIN' ? buildRoute('hrDashboard') : buildRoute('landing')}
                  className="inline-flex flex-col items-end rounded-lg px-3 py-2 font-medium text-[#0f172a] hover:bg-[#eef4f8] hover:text-[#0b2b43] transition-colors"
                >
                  {identity}
                  {role && <span className="uppercase tracking-wide text-xs text-[#6b7280] font-normal mt-0.5">{role}</span>}
                </Link>
              )}
            </div>
          </div>
        </Container>
        {isEmployeeRole && !isHrRole && (
          <div className="border-t border-[#e2e8f0]">
            <Container maxWidth="xl" className="py-3">
              <nav className="flex flex-wrap items-center gap-2 text-sm text-[#6b7280]">
                <Link
                  to={buildRoute('employeeJourney')}
                  className={`px-3 py-1 rounded-full border ${
                    isActiveRoute(ROUTE_DEFS.employeeJourney.path) && !location.pathname.includes('/wizard')
                      ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
                      : 'border-transparent hover:text-[#0b2b43]'
                  }`}
                >
                  Dashboard
                </Link>
                {assignmentId && (
                  <Link
                    to={`/employee/case/${assignmentId}/wizard/1`}
                    className={`px-3 py-1 rounded-full border ${
                      location.pathname.includes('/wizard')
                        ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    My Case
                  </Link>
                )}
                <Link
                  to={buildRoute('providers')}
                  className={`px-3 py-1 rounded-full border ${
                    isActiveRoute(ROUTE_DEFS.providers.path)
                      ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
                      : 'border-transparent hover:text-[#0b2b43]'
                  }`}
                >
                  Providers
                </Link>
                <Link
                  to={buildRoute('hrPolicy')}
                  className={`px-3 py-1 rounded-full border ${
                    isActiveRoute(ROUTE_DEFS.hrPolicy.path)
                      ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
                      : 'border-transparent hover:text-[#0b2b43]'
                  }`}
                >
                  HR Policy
                </Link>
                <Link
                  to={buildRoute('messages')}
                  className={`px-3 py-1 rounded-full border ${
                    isActiveRoute(ROUTE_DEFS.messages.path)
                      ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
                      : 'border-transparent hover:text-[#0b2b43]'
                  }`}
                >
                  Messages
                </Link>
                <Link
                  to={buildRoute('resources')}
                  className={`px-3 py-1 rounded-full border ${
                    isActiveRoute(ROUTE_DEFS.resources.path)
                      ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
                      : 'border-transparent hover:text-[#0b2b43]'
                  }`}
                >
                  Resources
                </Link>
              </nav>
            </Container>
          </div>
        )}
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
                    to={buildRoute('hrPolicyManagement')}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrPolicyManagement.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    Policy Management
                  </Link>
                  <Link
                    to={buildRoute('hrCompanyProfile')}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrCompanyProfile.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    Company Profile
                  </Link>
                  <Link
                    to={messagesRoute}
                    className={`px-3 py-1 rounded-full border ${
                      isActiveRoute(ROUTE_DEFS.hrMessages.path)
                        ? 'border-[#1d4ed8] text-[#1d4ed8] bg-[#eff6ff]'
                        : 'border-transparent hover:text-[#0b2b43]'
                    }`}
                  >
                    Messages
                  </Link>
                  {role === 'ADMIN' && (
                    <Link
                      to={buildRoute('adminConsole')}
                      className={`px-3 py-1 rounded-full border ${
                        isActiveRoute(ROUTE_DEFS.adminConsole.path)
                          ? 'border-[#0b2b43] text-[#0b2b43] bg-[#eef4f8]'
                          : 'border-transparent hover:text-[#0b2b43]'
                      }`}
                    >
                      Admin Console
                    </Link>
                  )}
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
                  {role === 'ADMIN' && (
                    <Link
                      to={buildRoute('employeeJourney')}
                      className={`px-3 py-1 rounded-full border ${
                        isActiveRoute(ROUTE_DEFS.employeeJourney.path)
                          ? 'border-[#059669] text-[#059669] bg-[#ecfdf5]'
                          : 'border-[#d1d5db] text-[#6b7280] hover:text-[#059669]'
                      }`}
                    >
                      Employee View
                    </Link>
                  )}
                </nav>
              </div>
              <div className="text-xs text-[#6b7280]">
                {selectedCaseId ? (
                  <span>
                    Case in use: {selectedCaseId.slice(0, 8)}…{identity ? ` · User: ${identity}` : ''}
                  </span>
                ) : (
                  <span>No case selected{identity ? ` · User: ${identity}` : ''}</span>
                )}
              </div>
            </Container>
          </div>
        )}
      </header>
      {adminContext?.impersonation && (
        <div className="bg-amber-50 border-b border-amber-200">
          <Container maxWidth="xl" className="py-2 flex items-center justify-between text-sm text-amber-900">
            <span>
              View-as mode: {adminContext.impersonation.mode.toUpperCase()} — {adminContext.impersonation.target_user_id}
            </span>
            <button
              onClick={async () => {
                await adminAPI.stopImpersonation();
                refreshAdminContext();
              }}
              className="text-xs px-3 py-1 rounded-full bg-amber-100 hover:bg-amber-200"
            >
              Stop view-as
            </button>
          </Container>
        </div>
      )}

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
