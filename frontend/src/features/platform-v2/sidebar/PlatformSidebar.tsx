import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Search,
  ChevronsUpDown,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { buildRoute, type RouteKey } from '../../../navigation/routes';
import { NAV_ICONS, type NavIconId } from './navIcons';

const COLLAPSE_KEY = 'platform_sidebar_collapsed';

type Badge = { label: string; tone?: 'accent' | 'new' | 'live' | 'count' };

type NavItem = {
  // NavIconId (not string) so an item with no NAV_ICONS entry fails tsc.
  id: NavIconId;
  name: string;
  to: string;
  badge?: Badge;
};

type NavSection = {
  label: string;
  items: NavItem[];
};

type Workspace = { initials: string; name: string };
type CurrentUser = { initials: string; name: string; role: string };

interface PlatformSidebarProps {
  workspace?: Workspace;
  user?: CurrentUser;
  initialCollapsed?: boolean;
  /** Optional override — when omitted, uses the default ReloPass section map. */
  sections?: NavSection[];
}

/**
 * Best-effort mapping from prototype items → real ReloPass routes. Items
 * without a real route yet point at the nearest landing surface so the link
 * is never broken. Replace these as new screens ship.
 */
function defaultSections(): NavSection[] {
  const r = (key: RouteKey) => buildRoute(key);
  return [
    {
      label: 'Employee',
      items: [
        { id: 'intake', name: 'Intake', to: r('employeeDashboard') },
        { id: 'detailed-intake', name: 'Detailed intake', to: r('employeeDashboard'), badge: { label: 'NEW', tone: 'new' } },
        { id: 'roadmap', name: 'Roadmap', to: r('employeeDashboard'), badge: { label: '3', tone: 'count' } },
        { id: 'documents', name: 'Documents', to: r('employeeTaskPage') },
        { id: 'dossier', name: 'Dossier & forms', to: r('employeeDashboard') },
        { id: 'service-providers', name: 'Service providers', to: r('services') },
        { id: 'inbox', name: 'Inbox', to: r('messages'), badge: { label: '3', tone: 'count' } },
      ],
    },
    {
      label: 'AI Engine',
      items: [
        { id: 'requirements-discovery', name: 'Requirements', to: r('resources'), badge: { label: 'LIVE', tone: 'live' } },
      ],
    },
    {
      label: 'HR Operations',
      items: [
        { id: 'company-profile', name: 'Company profile', to: r('hrCompanyProfile') },
        { id: 'mobility-control', name: 'Mobility control', to: r('hrCommandCenter'), badge: { label: '12', tone: 'count' } },
        { id: 'policy-builder', name: 'Policy Builder', to: r('hrPolicyBuilder'), badge: { label: 'NEW', tone: 'new' } },
        { id: 'policy-benefits', name: 'Policy & benefits', to: r('hrPolicy') },
        { id: 'policy-reality', name: 'Policy vs. Reality', to: r('hrAnalytics'), badge: { label: 'NEW', tone: 'new' } },
        { id: 'exceptions', name: 'Exceptions', to: r('hrReview') },
      ],
    },
    {
      label: 'Admin · ReloPass',
      items: [
        { id: 'admin-overview', name: 'Admin overview', to: r('adminOverview') },
        { id: 'admin-companies', name: 'Companies', to: r('adminCompanies') },
        { id: 'review-queue', name: 'Review queue', to: r('adminReviewQueue'), badge: { label: '24', tone: 'count' } },
        { id: 'ops-analytics', name: 'Ops analytics', to: r('adminOpsSla') },
        { id: 'workflow-analytics', name: 'Workflow analytics', to: r('adminOpsQueue') },
        { id: 'resources-cms', name: 'Resources CMS', to: r('adminResources') },
        { id: 'prospects', name: 'Prospects', to: r('adminProspects') },
        { id: 'integrations', name: 'Integrations', to: r('adminConsole') },
      ],
    },
  ];
}

function readCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === '1';
  } catch {
    return false;
  }
}

function badgeClasses(tone: Badge['tone']): string {
  switch (tone) {
    case 'new':
      return 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200';
    case 'live':
      return 'bg-rose-50 text-rose-600 ring-1 ring-inset ring-rose-200';
    case 'count':
      return 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200';
    case 'accent':
    default:
      return 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200';
  }
}

export const PlatformSidebar: React.FC<PlatformSidebarProps> = ({
  workspace = { initials: 'AE', name: 'Aurora Energy' },
  user = { initials: 'RP', name: 'Romain · ReloPass', role: 'Admin · superuser' },
  initialCollapsed,
  sections,
}) => {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState<boolean>(() =>
    typeof initialCollapsed === 'boolean' ? initialCollapsed : readCollapsed()
  );

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  const resolvedSections = useMemo(() => sections ?? defaultSections(), [sections]);

  const isActive = (to: string) => {
    if (!to || to === '#') return false;
    if (to === '/') return location.pathname === '/';
    return location.pathname === to || location.pathname.startsWith(`${to}/`);
  };

  const width = collapsed ? 'w-[72px]' : 'w-[260px]';

  return (
    <aside
      aria-label="Platform navigation"
      className={`${width} relative h-screen sticky top-0 shrink-0 border-r border-slate-200 bg-white text-slate-700 flex flex-col transition-[width] duration-200 ease-out`}
    >
      {/* Collapse toggle — floats over the right edge */}
      <Button unstyled
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="absolute -right-3 top-5 z-30 grid h-6 w-6 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-blue-500 hover:text-blue-600 hover:ring-4 hover:ring-blue-100"
      >
        {collapsed ? <PanelLeftOpen size={13} /> : <PanelLeftClose size={13} />}
      </Button>

      {/* Brand */}
      <div className={`flex items-center gap-2.5 border-b border-slate-100 px-3 pb-3 pt-3.5 ${collapsed ? 'justify-center' : ''}`}>
        <img
          src="/relopass-logo.png?v=3"
          width={122}
          height={128}
          alt=""
          className="h-6 w-6 rounded-md object-contain"
        />
        {!collapsed && (
          <div className="text-[14.5px] font-semibold tracking-tight text-slate-900">
            ReloPass <span className="font-medium text-slate-500">/ Platform</span>
          </div>
        )}
      </div>

      {/* Workspace selector */}
      <div className={`mx-2 mt-3 flex items-center gap-2 rounded-lg bg-slate-100/70 px-2.5 py-1.5 text-[12.5px] cursor-pointer hover:bg-slate-100 ${collapsed ? 'justify-center px-1.5' : ''}`}>
        <span className="grid h-[22px] w-[22px] place-items-center rounded-md bg-gradient-to-br from-teal-700 to-slate-900 text-[10px] font-bold text-white">
          {workspace.initials}
        </span>
        {!collapsed && (
          <>
            <span className="flex-1 truncate font-medium text-slate-800">{workspace.name}</span>
            <ChevronsUpDown size={12} className="text-slate-500" />
          </>
        )}
      </div>

      {/* Search */}
      <div className={`mx-2 mt-2 flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[12.5px] text-slate-500 focus-within:border-blue-400 focus-within:bg-white ${collapsed ? 'justify-center px-1.5' : ''}`}>
        <Search size={13} />
        {!collapsed && (
          <>
            <Input unstyled
              type="text"
              placeholder="Search cases, vendors…"
              className="min-w-0 flex-1 border-0 bg-transparent text-[12.5px] text-slate-800 outline-none placeholder:text-slate-500"
            />
            <span className="rounded border border-slate-200 bg-white px-1 py-px font-mono text-[10px] text-slate-500">⌘K</span>
          </>
        )}
      </div>

      {/* Nav sections */}
      <nav className="mt-1 flex-1 overflow-y-auto px-2 pb-3">
        {resolvedSections.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <div className="px-2.5 pb-1.5 pt-3.5 text-[10.5px] font-semibold uppercase tracking-[0.07em] text-slate-500">
                {section.label}
              </div>
            )}
            {collapsed && <div className="mt-3 border-t border-slate-100" aria-hidden="true" />}
            <div className="flex flex-col gap-px">
              {section.items.map((item) => {
                const active = isActive(item.to);
                const Icon = NAV_ICONS[item.id];
                return (
                  <Link
                    key={item.id}
                    to={item.to}
                    title={collapsed ? item.name : undefined}
                    className={`group relative flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors ${
                      active
                        ? 'bg-blue-50 text-blue-700'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    } ${collapsed ? 'justify-center' : ''}`}
                  >
                    {Icon && (
                      <Icon
                        size={16}
                        strokeWidth={1.75}
                        className={active ? 'opacity-100' : 'opacity-80 group-hover:opacity-100'}
                      />
                    )}
                    {!collapsed && (
                      <>
                        <span className="flex-1 truncate">{item.name}</span>
                        {item.badge && (
                          <span
                            className={`ml-auto rounded-full px-1.5 py-px text-[10.5px] font-semibold leading-4 ${badgeClasses(item.badge.tone)}`}
                          >
                            {item.badge.label}
                          </span>
                        )}
                      </>
                    )}
                    {collapsed && item.badge && (
                      <span
                        aria-hidden="true"
                        className={`absolute right-1 top-1 h-1.5 w-1.5 rounded-full ${
                          item.badge.tone === 'live'
                            ? 'bg-rose-500'
                            : item.badge.tone === 'new'
                              ? 'bg-emerald-500'
                              : 'bg-blue-500'
                        }`}
                      />
                    )}
                    {collapsed && (
                      <span className="pointer-events-none absolute left-full top-1/2 z-40 ml-2 -translate-y-1/2 translate-x-[-4px] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[11.5px] font-medium text-white opacity-0 shadow-lg transition-all group-hover:translate-x-0 group-hover:opacity-100">
                        {item.name}
                        {item.badge && (
                          <span className="ml-1.5 rounded bg-white/10 px-1 text-[10px] text-white/80">{item.badge.label}</span>
                        )}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* User foot */}
      <div className={`mt-auto border-t border-slate-100 px-2 py-2 ${collapsed ? '' : ''}`}>
        <div className={`flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-slate-100 cursor-pointer ${collapsed ? 'justify-center px-1.5' : ''}`}>
          <span className="grid h-7 w-7 place-items-center rounded-md bg-gradient-to-br from-slate-700 to-slate-900 text-[11px] font-semibold text-white">
            {user.initials}
          </span>
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-medium text-slate-900">{user.name}</div>
                <div className="truncate text-[11px] text-slate-500">{user.role}</div>
              </div>
              <ChevronRight size={14} className="text-slate-500" />
            </>
          )}
        </div>
      </div>
    </aside>
  );
};

export default PlatformSidebar;
