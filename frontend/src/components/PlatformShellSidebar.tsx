import React, { useEffect, useState } from 'react';
import { Button } from './antigravity/Button';
import { Link, useLocation } from 'react-router-dom';
import { PanelLeftClose, PanelLeftOpen, ChevronRight } from 'lucide-react';
import { NavIcon } from '../features/platform-v2/sidebar/navIcons';
import { ROUTE_DEFS, buildRoute } from '../navigation/routes';
import { getHrNotificationCounts, type HrNotificationCounts } from '../api/hrCatalog';
import { getAdminNotificationCounts, type AdminNotificationCounts } from '../api/adminCatalog';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';

// ── Types ──────────────────────────────────────────────────────────────────────

export type SidebarRole = 'EMPLOYEE' | 'HR' | 'ADMIN';

type BadgeVariant = 'count' | 'new' | 'live';
type BadgeSpec =
  | { kind: 'static'; variant: 'new' | 'live' }
  | { kind: 'static-count'; count: number }
  | { kind: 'dynamic'; getCount: (ctx: NotifContext) => number };

interface SidebarVisibilityCtx {
  role: SidebarRole;
  linkedCount: number;
}

interface SectionItem {
  id: string;
  label: string;
  /** Optional one-line hint shown below the label (not shown when collapsed). */
  hint?: string;
  to: string;
  /** Optional override per role (e.g. employee Inbox vs HR Inbox). */
  toByRole?: Partial<Record<SidebarRole, string>>;
  /** Exact route match — useful when path is the index of a section. */
  exact?: boolean;
  badge?: BadgeSpec;
  /** Hide this item conditionally (e.g. wizard tab is meaningless without a case). */
  hidden?: (ctx: SidebarVisibilityCtx) => boolean;
}

interface NavSection {
  label: string;
  minRole: SidebarRole;
  items: SectionItem[];
}

interface NotifContext {
  hr: HrNotificationCounts | null;
  admin: AdminNotificationCounts | null;
}

const ROLE_RANK: Record<SidebarRole, number> = { EMPLOYEE: 0, HR: 1, ADMIN: 2 };

// ── Section definitions ───────────────────────────────────────────────────────
// Single source of truth. Routes pulled from ROUTE_DEFS so renames cascade.

const SECTIONS: NavSection[] = [
  {
    label: 'Employee',
    minRole: 'EMPLOYEE',
    items: [
      { id: 'intake', label: 'My cases', to: ROUTE_DEFS.employeeDashboard.path, exact: true },
      {
        id: 'detailed-intake',
        label: 'Intake form',
        hint: 'Answer questions that shape your relocation case',
        to: ROUTE_DEFS.employeeIntake.path,
        // Wizard is meaningless without a linked case — hide until the user has one.
        // Admins keep it visible so they can preview the form.
        hidden: ({ linkedCount, role }) => role !== 'ADMIN' && linkedCount === 0,
      },
      { id: 'roadmap', label: 'Roadmap', to: ROUTE_DEFS.employeeDashboard.path, badge: { kind: 'static-count', count: 3 } },
      { id: 'documents', label: 'Tasks', hint: 'Documents and actions requested by your HR team', to: ROUTE_DEFS.employeeTaskPage.path },
      { id: 'dossier', label: 'Dossier & forms', to: ROUTE_DEFS.employeeDashboard.path },
      { id: 'service-providers', label: 'Service providers', to: ROUTE_DEFS.services.path },
      { id: 'benefit-comparison', label: 'Benefit comparison', to: ROUTE_DEFS.employeeBenefitsComparison.path },
      {
        id: 'inbox',
        label: 'Inbox',
        to: ROUTE_DEFS.messages.path,
        toByRole: { HR: ROUTE_DEFS.hrMessages.path, ADMIN: ROUTE_DEFS.hrMessages.path },
        badge: { kind: 'static-count', count: 3 },
      },
    ],
  },
  {
    label: 'HR Operations',
    minRole: 'HR',
    items: [
      // P10-followup #7 — Requirements item routes to /resources so clicking it
      // lands on the page with H1 'Requirements' (Resources.tsx, renamed in P10).
      // Mobility policy is still reachable via the sibling 'Policy' nav item
      // ('policy-benefits' below) which points at ROUTE_DEFS.hrPolicy.path.
      { id: 'requirements-discovery', label: 'Requirements', to: ROUTE_DEFS.resources.path, badge: { kind: 'static', variant: 'live' } },
      { id: 'company-profile', label: 'Company profile', to: ROUTE_DEFS.hrCompanyProfile.path, exact: true },
      {
        id: 'mobility-control',
        label: 'Mobility center',
        to: ROUTE_DEFS.hrCommandCenter.path,
        exact: true,
        badge: { kind: 'static-count', count: 12 },
      },
      { id: 'policy-benefits', label: 'Policy', to: ROUTE_DEFS.hrPolicy.path },
      { id: 'provider-status', label: 'Provider status', to: ROUTE_DEFS.hrProviderGrid.path },
      { id: 'exceptions', label: 'Exceptions', to: ROUTE_DEFS.hrExceptions.path },
      { id: 'ai-decisions', label: 'AI decisions', to: ROUTE_DEFS.hrAiDecisions.path },
    ],
  },
  {
    label: 'Admin · ReloPass',
    minRole: 'ADMIN',
    items: [
      { id: 'admin-overview', label: 'Admin overview', to: ROUTE_DEFS.adminOverview.path, exact: true },
      { id: 'admin-companies', label: 'Companies', to: ROUTE_DEFS.adminCompanies.path },
      {
        id: 'review-queue',
        label: 'Review queue',
        to: ROUTE_DEFS.adminReviewQueue.path,
        badge: { kind: 'dynamic', getCount: (c) => c.admin?.pending_tickets ?? 24 },
      },
      { id: 'ops-analytics', label: 'Ops analytics', to: ROUTE_DEFS.adminOps.path },
      { id: 'workflow-analytics', label: 'Workflow analytics', to: ROUTE_DEFS.adminOpsQueue.path },
      { id: 'resources-cms', label: 'Resources CMS', to: ROUTE_DEFS.adminResources.path },
      { id: 'form-templates', label: 'Form templates', to: ROUTE_DEFS.adminFormTemplates.path, badge: { kind: 'static', variant: 'new' } },
      { id: 'prospects', label: 'Prospects', to: ROUTE_DEFS.adminProspects.path },
      {
        id: 'integrations',
        label: 'Integrations',
        to: ROUTE_DEFS.adminCatalogQueue.path,
        badge: { kind: 'dynamic', getCount: (c) => c.admin?.pending_tickets ?? 0 },
      },
    ],
  },
];

// ── Sub-pieces ────────────────────────────────────────────────────────────────

const Badge: React.FC<{ count?: number; variant?: BadgeVariant }> = ({ count, variant = 'count' }) => {
  if (variant === 'new') {
    return (
      <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold bg-accent-50 text-accent-500 border border-accent-100">
        NEW
      </span>
    );
  }
  if (variant === 'live') {
    return (
      <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-100">
        LIVE
      </span>
    );
  }
  if (!count || count <= 0) return null;
  return (
    <span className="ml-auto min-w-[1.25rem] px-1 text-center rounded-full bg-slate-200 text-slate-700 text-[10px] font-semibold leading-5">
      {count > 99 ? '99+' : count}
    </span>
  );
};

const SectionHeading: React.FC<{ label: string; count?: number; collapsed: boolean }> = ({ label, count, collapsed }) => {
  if (collapsed) return <div className="mt-3 mx-2 border-t border-slate-100" aria-hidden="true" />;
  return (
    <div className="flex items-center gap-1.5 px-3 pt-5 pb-1">
      <span className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase">{label}</span>
      {count !== undefined && <span className="text-[10px] text-slate-300 font-medium">{count}</span>}
    </div>
  );
};

// ── Props ─────────────────────────────────────────────────────────────────────

export interface PlatformShellSidebarProps {
  role: SidebarRole;
  /** Optional slot for the company widget under the brand (CompanySwitcher / CompanyBrand). */
  companySlot?: React.ReactNode;
  /** Footer identity. Defaults to a sensible placeholder if absent. */
  user?: { initials: string; name: string; role: string };
}

// ── Collapse persistence ──────────────────────────────────────────────────────

const COLLAPSE_KEY = 'platform_sidebar_collapsed';

function readCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === '1';
  } catch {
    return false;
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export const PlatformShellSidebar: React.FC<PlatformShellSidebarProps> = ({ role, companySlot, user }) => {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState<boolean>(() => readCollapsed());

  // Persist + cross-tab sync
  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === COLLAPSE_KEY) setCollapsed(e.newValue === '1');
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // Notification polling — only what the visible sections need
  const [hrNotif, setHrNotif] = useState<HrNotificationCounts | null>(null);
  const [adminNotif, setAdminNotif] = useState<AdminNotificationCounts | null>(null);
  const rank = ROLE_RANK[role];

  useEffect(() => {
    if (rank < ROLE_RANK.HR) return;
    let cancelled = false;
    const fetchHr = () => {
      void getHrNotificationCounts()
        .then((c) => { if (!cancelled) setHrNotif(c); })
        .catch(() => {});
    };
    fetchHr();
    const id = window.setInterval(fetchHr, 60_000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [rank]);

  useEffect(() => {
    if (rank < ROLE_RANK.ADMIN) return;
    let cancelled = false;
    const fetchAdmin = () => {
      void getAdminNotificationCounts()
        .then((c) => { if (!cancelled) setAdminNotif(c); })
        .catch(() => {});
    };
    fetchAdmin();
    const id = window.setInterval(fetchAdmin, 60_000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [rank]);

  const notifCtx: NotifContext = { hr: hrNotif, admin: adminNotif };

  // Extract caseId from the URL when on a case-scoped employee route
  // e.g. /employee/case/43556892-2f33-4ab1-8533-9c11095e5565/wizard/1 → caseId
  const urlCaseId = location.pathname.match(/\/employee\/case\/([^/]+)/)?.[1] ?? null;

  // Fall back to the last-known caseId (SelectedCaseContext / localStorage), then to the
  // employee's primary linked case, so sidebar links resolve to the case-scoped roadmap/dossier
  // even from /employee/dashboard where there is no case in the URL and nothing was selected yet.
  const { selectedCaseId } = useSelectedCase();
  const { linkedCount, primaryCaseId } = useEmployeeAssignment();
  const effectiveCaseId = urlCaseId ?? selectedCaseId ?? primaryCaseId;

  // Resolve the effective `to` for an item, allowing case-scoped overrides
  const resolveItemTo = (item: SectionItem): string => {
    if (item.id === 'roadmap' && effectiveCaseId) {
      return buildRoute('employeeCaseRoadmap', { caseId: effectiveCaseId });
    }
    if (item.id === 'dossier' && effectiveCaseId) {
      return buildRoute('employeeCaseDossier', { caseId: effectiveCaseId });
    }
    return item.toByRole?.[role] ?? item.to;
  };

  const isActive = (item: SectionItem) => {
    const path = resolveItemTo(item);
    if (item.exact) return location.pathname === path;
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const visibilityCtx: SidebarVisibilityCtx = { role, linkedCount };
  const visibleSections = SECTIONS
    .filter((s) => ROLE_RANK[s.minRole] <= rank)
    .map((s) => {
      // A higher-role user (e.g. HR) inherits lower-persona sections via the rank
      // model, but should NOT see that persona's exclusive surfaces — only items
      // that explicitly declare a route for their role (e.g. the shared Inbox via
      // toByRole). Admin keeps everything for cross-persona preview.
      const borrowed = ROLE_RANK[s.minRole] < rank && role !== 'ADMIN';
      return {
        ...s,
        // Suppress the persona heading on a borrowed section: its surviving shared
        // items (Inbox) float at the top rather than under a misleading "Employee" label.
        borrowed,
        items: s.items.filter((item) => {
          if (item.hidden?.(visibilityCtx)) return false;
          if (borrowed) return Boolean(item.toByRole?.[role]);
          return true;
        }),
      };
    })
    .filter((s) => s.items.length > 0);

  return (
    <aside
      aria-label="Platform navigation"
      className={`${collapsed ? 'w-[64px]' : 'w-[240px]'} shrink-0 flex flex-col bg-white border-r border-slate-200 overflow-y-auto transition-[width] duration-200 ease-out`}
    >
      {/* Brand + collapse toggle */}
      <div className={`flex items-center border-b border-slate-100 px-3 py-3 ${collapsed ? 'justify-center' : 'gap-2'}`}>
        {!collapsed && (
          <>
            <img
              src="/logo.svg"
              alt="ReloPass"
              className="h-6 w-auto"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <span className="text-sm font-semibold text-slate-900">ReloPass</span>
            <span className="text-slate-400 text-sm">/ Platform</span>
            <Button unstyled
              type="button"
              onClick={() => setCollapsed(true)}
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              className="ml-auto grid h-6 w-6 place-items-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            >
              <PanelLeftClose size={14} />
            </Button>
          </>
        )}
        {collapsed && (
          <Button unstyled
            type="button"
            onClick={() => setCollapsed(false)}
            aria-label="Expand sidebar"
            title="Expand sidebar"
            className="grid h-7 w-7 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          >
            <PanelLeftOpen size={15} />
          </Button>
        )}
      </div>

      {/* Company switcher / brand */}
      {!collapsed && companySlot && (
        <div className="px-3 py-2 border-b border-slate-100">{companySlot}</div>
      )}

      {/* Search */}
      {!collapsed && (
        <div className="px-3 py-2 border-b border-slate-100">
          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-200">
            <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="text-xs text-slate-400 flex-1">Search cases and vendors</span>
            <kbd className="text-[10px] text-slate-300 border border-slate-200 rounded px-1">⌘K</kbd>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-2 pb-4">
        {visibleSections.map((section) => (
          <React.Fragment key={section.label}>
            {!section.borrowed && (
              <SectionHeading
                label={section.label}
                count={section.items.length}
                collapsed={collapsed}
              />
            )}
            {section.items.map((item) => {
              const active = isActive(item);
              const to = resolveItemTo(item);

              let badgeVariant: BadgeVariant | undefined;
              let badgeCount: number | undefined;
              if (item.badge) {
                if (item.badge.kind === 'static') {
                  badgeVariant = item.badge.variant;
                } else if (item.badge.kind === 'static-count') {
                  badgeCount = item.badge.count;
                } else {
                  badgeCount = item.badge.getCount(notifCtx);
                }
              }

              return (
                <Link
                  key={item.id}
                  to={to}
                  title={item.label}
                  className={`group relative flex items-center gap-2.5 rounded-lg text-sm transition-colors ${
                    collapsed ? 'justify-center px-2 py-2' : 'px-3 py-1.5'
                  } ${
                    active
                      ? 'bg-[#0b2b43]/8 text-[#0b2b43] font-medium'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <NavIcon
                    id={item.id}
                    size={15}
                    className={`shrink-0 ${active ? 'opacity-100' : 'opacity-75 group-hover:opacity-100'}`}
                  />
                  {!collapsed && (
                    <>
                      <span className="flex-1 min-w-0">
                        <span className="block truncate">{item.label}</span>
                        {item.hint && (
                          <span className="block truncate text-[10px] leading-tight mt-0.5 font-normal text-slate-400 group-hover:text-slate-500">
                            {item.hint}
                          </span>
                        )}
                      </span>
                      <Badge count={badgeCount} variant={badgeVariant} />
                    </>
                  )}
                  {collapsed && badgeCount !== undefined && badgeCount > 0 && (
                    <span aria-hidden="true" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-blue-500" />
                  )}
                  {collapsed && badgeVariant === 'new' && (
                    <span aria-hidden="true" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-accent-500" />
                  )}
                  {collapsed && badgeVariant === 'live' && (
                    <span aria-hidden="true" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  )}
                  {/* Tooltip when collapsed */}
                  {collapsed && (
                    <span className="pointer-events-none absolute left-full top-1/2 z-40 ml-2 -translate-y-1/2 translate-x-[-4px] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[11.5px] font-medium text-white opacity-0 shadow-lg transition-all group-hover:translate-x-0 group-hover:opacity-100">
                      {item.label}
                    </span>
                  )}
                </Link>
              );
            })}
          </React.Fragment>
        ))}
      </nav>

      {/* User footer */}
      <div className="px-3 py-3 border-t border-slate-100">
        <div className={`flex items-center gap-2 ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-semibold text-slate-600 shrink-0">
            {user?.initials ?? 'RP'}
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-900 truncate">{user?.name ?? 'ReloPass'}</p>
                <p className="text-[10px] text-slate-400 truncate">{user?.role ?? role.toLowerCase()}</p>
              </div>
              <Button unstyled className="text-slate-400 hover:text-slate-600 shrink-0">
                <ChevronRight size={14} />
              </Button>
            </>
          )}
        </div>
      </div>
    </aside>
  );
};

export default PlatformShellSidebar;
