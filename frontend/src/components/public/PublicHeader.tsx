import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Container } from '../antigravity';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';

const logoUrl = '/relopass-logo.png?v=1';

const PUBLIC_NAV = [
  { key: 'platform', label: 'Platform', path: ROUTE_DEFS.platform.path },
  { key: 'why', label: 'Why ReloPass', path: ROUTE_DEFS.why.path },
  { key: 'trust', label: 'How it works', path: ROUTE_DEFS.trust.path },
  { key: 'access', label: 'Get started', path: ROUTE_DEFS.access.path },
] as const;

export const PublicHeader: React.FC = () => {
  const location = useLocation();
  const role = getAuthItem('relopass_role');
  const [mobileOpen, setMobileOpen] = useState(false);

  const dashboardPath =
    role === 'EMPLOYEE'
      ? ROUTE_DEFS.employeeDashboard.path
      : role === 'HR' || role === 'ADMIN'
        ? ROUTE_DEFS.hrDashboard.path
        : null;

  const isActive = (path: string) =>
    path === '/'
      ? location.pathname === '/'
      : location.pathname === path || location.pathname.startsWith(`${path}/`);

  return (
    <header className="sticky top-0 z-50 border-b border-marketing-border bg-marketing-surface/95 backdrop-blur-sm">
      <Container maxWidth="xl" className="py-4 sm:py-5">
        <div className="flex items-center justify-between gap-6">
          <Link
            to={buildRoute('landing')}
            className="flex items-center gap-3 shrink-0"
            aria-label="ReloPass home"
          >
            <img
              src={logoUrl}
              alt="ReloPass"
              className="h-10 w-10 sm:h-12 sm:w-12 rounded-xl object-contain"
            />
            <span className="text-lg font-semibold text-marketing-primary tracking-tight hidden sm:inline">
              ReloPass
            </span>
          </Link>

          <nav
            className={`absolute top-full left-0 right-0 mt-0 border-b border-marketing-border bg-marketing-surface sm:static sm:border-0 sm:bg-transparent sm:mt-0 ${
              mobileOpen ? 'block' : 'hidden sm:block'
            }`}
            aria-label="Main navigation"
          >
            <ul className="flex flex-col sm:flex-row items-stretch sm:items-center gap-0 sm:gap-1 py-4 sm:py-0 px-4 sm:px-0">
              {PUBLIC_NAV.map((item) => (
                <li key={item.key}>
                  <Link
                    to={item.path}
                    onClick={() => setMobileOpen(false)}
                    className={`block px-4 py-3 sm:px-3 sm:py-2 text-sm font-medium rounded-lg transition-colors ${
                      isActive(item.path)
                        ? 'text-marketing-primary bg-marketing-surface-muted'
                        : 'text-marketing-text-muted hover:text-marketing-primary hover:bg-marketing-surface-muted/60'
                    }`}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="flex items-center gap-2 sm:gap-3">
            {dashboardPath ? (
              <Link
                to={dashboardPath}
                onClick={() => setMobileOpen(false)}
                className="px-4 py-2 text-sm font-medium text-marketing-primary hover:text-marketing-accent transition-colors"
              >
                Dashboard
              </Link>
            ) : null}
            <Link
              to={`${buildRoute('auth')}?mode=login`}
              onClick={() => setMobileOpen(false)}
              className="px-4 py-2 text-sm font-medium text-marketing-text-muted hover:text-marketing-primary transition-colors"
            >
              Sign in
            </Link>
            <button
              type="button"
              onClick={() => setMobileOpen(!mobileOpen)}
              className="p-2 rounded-lg text-marketing-text-muted hover:bg-marketing-surface-muted sm:hidden"
              aria-expanded={mobileOpen}
              aria-label="Toggle menu"
            >
              {mobileOpen ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </Container>
    </header>
  );
};
