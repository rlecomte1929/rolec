import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { getAuthItem, normalizeStoredRole } from '../utils/demo';
import { authAPI } from '../api/client';
import { useBrandingConfig } from '../hooks/useBrandingConfig';
import { getNavigationError } from '../navigation/safeNavigate';
import { buildRoute, homeRouteKeyForRole } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { setPreferredEmployeeAssignmentId } from '../utils/employeeAssignmentScope';
import { useAdminContext } from '../features/admin/useAdminContext';
import { adminAPI } from '../api/client';
import { ChangelogBell } from './ChangelogBell';
import { RoleSwitcher } from './RoleSwitcher';
import { Breadcrumb } from './Breadcrumb';
import { Button } from './antigravity/Button';
import { CompanyBrand } from './CompanyBrand';
import { FeedbackWidget } from './FeedbackWidget';
import { GlobalApiErrorBanner } from './GlobalApiErrorBanner';
import { PlatformShellSidebar, type SidebarRole } from './PlatformShellSidebar';

function deriveInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'RP';
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}

function sidebarRole(role: string | null | undefined): SidebarRole {
  const r = (role ?? '').toUpperCase();
  if (r === 'ADMIN') return 'ADMIN';
  if (r === 'HR') return 'HR';
  return 'EMPLOYEE';
}

const LogoutButton: React.FC = () => {
  const [isLoggingOut, setIsLoggingOut] = React.useState(false);
  return (
    <Button unstyled
      onClick={async () => {
        if (isLoggingOut) return;
        setIsLoggingOut(true);
        try {
          await authAPI.logout();
          // AIQ-990: land on the login page after sign-out, not the marketing
          // homepage — the user just left the app and most likely wants to sign
          // back in, not read the landing page.
          window.location.replace(buildRoute('login'));
        } catch {
          setIsLoggingOut(false);
        }
      }}
      disabled={isLoggingOut}
      className="text-xs text-slate-500 hover:text-slate-800 disabled:opacity-60"
    >
      {isLoggingOut ? 'Logging out…' : 'Log out'}
    </Button>
  );
};

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  /**
   * Top-level breadcrumb section, e.g. 'HR Operations' or 'Employee'.
   * Mirrors the sidebar SECTIONS taxonomy. When omitted the breadcrumb
   * collapses to two segments (ReloPass / Page) — present for backward
   * compatibility with pages not yet migrated to the 3-segment standard.
   */
  section?: string;
  /**
   * When true, the main content area drops the max-w-7xl cap and fills the
   * viewport (with a small gutter). Use for dense dashboards where the
   * standard 1280px cap leaves dead space on wide monitors.
   */
  wide?: boolean;
  /**
   * Optional intermediate parent page for breadcrumb back-navigation.
   * Renders a clickable crumb between section and the current page title.
   * Example: { label: 'Mobility command center', href: '/hr/command-center' }
   */
  parent?: { label: string; href: string };
}

export const AppShell: React.FC<AppShellProps> = ({ children, title, subtitle, section, wide = false, parent }) => {
  const name = getAuthItem('relopass_name');
  const role = normalizeStoredRole(getAuthItem('relopass_role'));
  const identity = name || getAuthItem('relopass_email') || getAuthItem('relopass_username');
  const location = useLocation();
  const [navError, setNavError] = useState<string | null>(getNavigationError());
  // AIQ-1017: on mobile (<md) the sidebar collapses into a slide-in drawer
  // toggled from the topbar hamburger. Desktop is unchanged (inline sidebar).
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const isEmployeeRole = role === 'EMPLOYEE' || role === 'ADMIN';

  // GAP 10: Apply company branding CSS vars (primary_colour etc.) to :root
  useBrandingConfig();
  const { linkedCount, isLoading: employeeAssignmentLoading } = useEmployeeAssignment();
  const { context: adminContext, refresh: refreshAdminContext } = useAdminContext();

  useRegisterNav('AppShell', [
    { label: 'Employee view', routeKey: 'employeeDashboard' },
    { label: 'HR view', routeKey: 'hrDashboard' },
  ]);

  useEffect(() => {
    const handler = (event: Event) => {
      const custom = event as CustomEvent<string>;
      setNavError(custom.detail || null);
    };
    window.addEventListener('nav-error', handler);
    return () => window.removeEventListener('nav-error', handler);
  }, []);

  // AIQ-1017: close the mobile nav drawer on route change so a tap-through
  // doesn't leave the overlay covering the new page.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  // A11Y-3: give every in-app route a meaningful tab/screen-reader title
  // (the static index.html title otherwise persists across the whole app).
  useEffect(() => {
    document.title = title ? `ReloPass — ${title}` : 'ReloPass';
  }, [title]);

  // A11Y-4: announce route changes to assistive tech and move focus to the main
  // content on navigation (only on actual route change, not in-page state changes).
  const [routeAnnouncement, setRouteAnnouncement] = useState('');
  useEffect(() => {
    setRouteAnnouncement(`${title || section || 'Page'} loaded`);
    document.getElementById('main-content')?.focus();
  }, [location.pathname]);

  useEffect(() => {
    if (!isEmployeeRole) return;
    const id = location.pathname.match(/^\/employee\/case\/([^/]+)/)?.[1]?.trim();
    if (!id) return;
    if (
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)
    ) {
      return;
    }
    setPreferredEmployeeAssignmentId(id);
  }, [location.pathname, isEmployeeRole]);

  const homeHref = buildRoute(
    getAuthItem('relopass_token') ? homeRouteKeyForRole(getAuthItem('relopass_role')) : 'landing'
  );

  const sbRole = sidebarRole(role);
  const userInitials = deriveInitials(name || identity || 'RP');
  const showEmployeeBanner =
    sbRole !== 'ADMIN' && isEmployeeRole && !employeeAssignmentLoading && linkedCount === 0;

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 text-slate-800">

      {/* AIQ-397: skip-link for keyboard users — visually hidden until focused,
          then jumps over the sidebar + topbar straight to the page content. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-[#0b2b43] focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:shadow-lg"
      >
        Skip to main content
      </a>

      {/* A11Y-4: visually-hidden live region announces the page on route change. */}
      <div aria-live="polite" className="sr-only">{routeAnnouncement}</div>

      {/* AIQ-1017: mobile backdrop — only rendered when the drawer is open, below md. */}
      {mobileNavOpen && (
        // eslint-disable-next-line local/no-clickable-div -- presentational mouse-dismiss overlay (aria-hidden); keyboard users dismiss via the panel's own controls
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          aria-hidden="true"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      {/* AIQ-1017: one sidebar instance. Desktop (md+): static inline flex child,
          unchanged. Mobile (<md): fixed slide-in drawer toggled by the topbar
          hamburger. A tap inside closes it so nav links dismiss the drawer. */}
      <div
        className={`fixed inset-y-0 left-0 z-50 flex transition-transform duration-200 ease-out md:static md:z-auto md:translate-x-0 md:transition-none ${
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <PlatformShellSidebar
          role={sbRole}
          companySlot={role !== 'ADMIN' ? <CompanyBrand /> : null}
          user={{
            initials: userInitials,
            name: identity ? `${identity}` : 'ReloPass user',
            role: role ? role.toLowerCase() : '',
          }}
        />
      </div>

      {/* ── Right side: topbar + banners + main + footer ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Slim topbar — breadcrumb moved inline above H1 (P4/AIQ-408).
            Topbar now carries only user-context controls; consistent across
            AppShell-backed pages and v2 custom-layout pages. */}
        <header className="flex items-center justify-between gap-2 px-4 md:px-6 py-3 bg-white border-b border-slate-200 shrink-0">
          {/* AIQ-1017: hamburger to open the nav drawer — mobile only. */}
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation menu"
            aria-expanded={mobileNavOpen}
            className="md:hidden grid h-9 w-9 shrink-0 place-items-center rounded-md text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="flex items-center gap-3 shrink-0 md:ml-auto">
            <RoleSwitcher />
            <ChangelogBell />
            <LogoutButton />
            {identity && (
              <Link
                to={homeHref}
                className="inline-flex flex-col items-end rounded-lg px-3 py-1.5 font-medium text-slate-900 hover:bg-slate-100 transition-colors"
              >
                <span className="text-xs leading-tight">{identity}</span>
                {role && (
                  <span className="text-[10px] uppercase tracking-wide text-slate-400 font-normal">
                    {role}
                  </span>
                )}
              </Link>
            )}
          </div>
        </header>

        {/* Banners */}
        {/* B13: global API unavailability banner (network error / timeout) */}
        <GlobalApiErrorBanner />

        {showEmployeeBanner && (
          <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 text-sm text-amber-900 shrink-0">
            <span className="mr-2">⏳</span>
            Your account isn&apos;t linked to a company assignment yet — most features are on hold.
            Use the <strong>Dashboard</strong> to claim your case, or wait for HR to match your email.
          </div>
        )}

        {adminContext?.impersonation && (
          <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 flex items-center justify-between text-sm text-amber-900 shrink-0">
            <span>
              View-as mode: {adminContext.impersonation.mode.toUpperCase()} ·{' '}
              {adminContext.impersonation.target_user_id}
            </span>
            <Button unstyled
              onClick={async () => {
                await adminAPI.stopImpersonation();
                void refreshAdminContext();
              }}
              className="text-xs px-3 py-1 rounded-full bg-amber-100 hover:bg-amber-200"
            >
              Stop view-as
            </Button>
          </div>
        )}

        {navError && (
          <div className="bg-rose-50 border-b border-rose-200 text-rose-800 text-sm px-6 py-2 shrink-0">
            Navigation blocked: {navError}
          </div>
        )}

        {/* Main scrollable area */}
        <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto outline-none">
          <div className={wide ? 'px-4 py-6 md:px-6' : 'px-4 py-6 md:px-8 md:py-7 max-w-7xl mx-auto'}>
            {title && (
              <div className="mb-6">
                <Breadcrumb section={section} title={title} homeHref={homeHref} parent={parent} className="mb-3" />
                <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
                {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
              </div>
            )}
            {children}
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t border-slate-200 bg-white px-6 py-3 text-xs text-slate-500 shrink-0">
          {/* Legal disclaimer: requires legal review before translation for EU/APAC locales. Do not translate without sign-off. */}
          ReloPass is not a legal adviser. Verify immigration requirements with qualified counsel.
        </footer>
      </div>

      <FeedbackWidget userId={getAuthItem('relopass_user_id')} />
    </div>
  );
};
