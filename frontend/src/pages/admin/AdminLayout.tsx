import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useMatch, useNavigate } from 'react-router-dom';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';
import { getAdminNotificationCounts, type AdminNotificationCounts } from '../../api/adminCatalog';
import { getAuthItem } from '../../utils/demo';
import { useAdminViewingCompany } from '../../features/admin/AdminViewingCompanyContext';
import type { AdminCompany } from '../../types';

interface Props {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Extra content rendered inline with the page heading (e.g. scope badges). */
  headerRight?: React.ReactNode;
}

// ── Sidebar badge ─────────────────────────────────────────────────────────────

const Badge: React.FC<{ count?: number; label?: string; variant?: 'count' | 'new' | 'live' }> = ({
  count,
  label,
  variant = 'count',
}) => {
  if (variant === 'new') return (
    <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-500 border border-indigo-100">
      NEW
    </span>
  );
  if (variant === 'live') return (
    <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-100">
      LIVE
    </span>
  );
  if (label) return (
    <span className="ml-auto text-[10px] font-semibold text-slate-400">{label}</span>
  );
  if (!count || count <= 0) return null;
  return (
    <span className="ml-auto min-w-[1.25rem] px-1 text-center rounded-full bg-slate-200 text-slate-700 text-[10px] font-semibold leading-5">
      {count > 99 ? '99+' : count}
    </span>
  );
};

// ── Nav item ──────────────────────────────────────────────────────────────────

interface NavItemProps {
  to: string;
  label: string;
  active: boolean;
  badge?: number;
  badgeVariant?: 'count' | 'new' | 'live';
  badgeLabel?: string;
}

const NavItem: React.FC<NavItemProps> = ({ to, label, active, badge, badgeVariant, badgeLabel }) => (
  <Link
    to={to}
    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
      active
        ? 'bg-[#0b2b43]/8 text-[#0b2b43] font-medium'
        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
    }`}
  >
    <span className="flex-1 truncate">{label}</span>
    <Badge count={badge} label={badgeLabel} variant={badgeVariant} />
  </Link>
);

// ── Section heading ───────────────────────────────────────────────────────────

const SectionHeading: React.FC<{ label: string; count?: number }> = ({ label, count }) => (
  <div className="flex items-center gap-1.5 px-3 pt-5 pb-1">
    <span className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase">{label}</span>
    {count !== undefined && (
      <span className="text-[10px] text-slate-300 font-medium">{count}</span>
    )}
  </div>
);

// ── Main layout ───────────────────────────────────────────────────────────────

export const AdminLayout: React.FC<Props> = ({ title, subtitle, children, headerRight }) => {
  const location = useLocation();
  const userName = getAuthItem('relopass_name') ?? 'Romain';

  const isActive = (path: string, exact?: boolean) =>
    exact
      ? location.pathname === path
      : location.pathname === path || location.pathname.startsWith(`${path}/`);

  const [adminNotif, setAdminNotif] = useState<AdminNotificationCounts | null>(null);
  useEffect(() => {
    let cancelled = false;
    const fetchOnce = () => {
      void getAdminNotificationCounts()
        .then((c) => { if (!cancelled) setAdminNotif(c); })
        .catch(() => {});
    };
    fetchOnce();
    const id = window.setInterval(fetchOnce, 60_000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  const pendingTickets = adminNotif?.pending_tickets ?? 0;

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">

      {/* ── Sidebar ── */}
      <aside className="w-[200px] shrink-0 flex flex-col bg-white border-r border-slate-200 overflow-y-auto">

        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-4 border-b border-slate-100">
          <img src="/logo.svg" alt="ReloPass" className="h-6 w-auto"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
          <span className="text-sm font-semibold text-slate-900">ReloPass</span>
          <span className="text-slate-400 text-sm">/ Platform</span>
        </div>

        {/* Company switcher */}
        <div className="px-3 py-2 border-b border-slate-100">
          <CompanySwitcher />
        </div>

        {/* Search */}
        <div className="px-3 py-2 border-b border-slate-100">
          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-200">
            <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="text-xs text-slate-400 flex-1">Search cases, vendors…</span>
            <kbd className="text-[10px] text-slate-300 border border-slate-200 rounded px-1">⌘K</kbd>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 pb-4">

          {/* EMPLOYEE */}
          <SectionHeading label="Employee" count={5} />
          <NavItem to={buildRoute('employeeDashboard')} label="Intake" active={isActive(ROUTE_DEFS.employeeDashboard.path, true)} />
          <NavItem to={buildRoute('employeeDashboard')} label="Detailed intake" active={false} badgeVariant="new" />
          <NavItem to={buildRoute('employeeDashboard')} label="Roadmap" active={false} badge={3} />
          <NavItem to={buildRoute('employeeDashboard')} label="Documents" active={false} />
          <NavItem to={buildRoute('employeeDashboard')} label="Dossier & forms" active={false} />
          <NavItem to={buildRoute('employeeDashboard')} label="Service providers" active={false} />
          <NavItem to={buildRoute('employeeTaskPage')} label="Inbox" active={isActive(ROUTE_DEFS.employeeTaskPage.path)} badge={3} />

          {/* AI ENGINE */}
          <SectionHeading label="AI Engine" />
          <NavItem to={buildRoute('employeeDashboard')} label="Requirements discovery" active={false} badgeVariant="live" />

          {/* HR OPERATIONS */}
          <SectionHeading label="HR Operations" count={5} />
          <NavItem to={buildRoute('hrCompanyProfile')} label="Company profile" active={isActive(ROUTE_DEFS.hrCompanyProfile.path, true)} />
          <NavItem to={buildRoute('hrCommandCenter')} label="Mobility control" active={isActive(ROUTE_DEFS.hrCommandCenter.path, true)} badge={12} />
          <NavItem to={buildRoute('hrPolicyBuilder')} label="Policy Builder" active={isActive(ROUTE_DEFS.hrPolicyBuilder.path)} badgeVariant="new" />
          <NavItem to={buildRoute('hrPolicy')} label="Policy & benefits" active={isActive(ROUTE_DEFS.hrPolicy.path)} />
          <NavItem to={buildRoute('hrProviderGrid')} label="Provider status" active={isActive(ROUTE_DEFS.hrProviderGrid.path)} badgeVariant="new" />
          <NavItem to={buildRoute('hrCommandCenter')} label="Exceptions" active={false} />

          {/* ADMIN · RELOPASS */}
          <SectionHeading label="Admin · ReloPass" count={5} />
          <NavItem to={buildRoute('adminOverview')} label="Admin overview"
            active={isActive(ROUTE_DEFS.adminOverview.path, true)} />
          <NavItem to={buildRoute('adminCompanies')} label="Companies"
            active={isActive(ROUTE_DEFS.adminCompanies.path)} />
          <NavItem to={buildRoute('adminReviewQueue')} label="Review queue"
            active={isActive(ROUTE_DEFS.adminReviewQueue.path)}
            badge={pendingTickets || 24} />
          <NavItem to={buildRoute('adminOpsSla')} label="Ops analytics"
            active={isActive(ROUTE_DEFS.adminOpsSla.path)} />
          <NavItem to={buildRoute('adminOpsQueue')} label="Workflow analytics"
            active={isActive(ROUTE_DEFS.adminOpsQueue.path)} />
          <NavItem to={buildRoute('adminResources')} label="Resources CMS"
            active={isActive(ROUTE_DEFS.adminResources.path)} />
          <NavItem to={buildRoute('adminProspects')} label="Prospects"
            active={isActive(ROUTE_DEFS.adminProspects.path)} />
          <NavItem to={buildRoute('adminCatalogQueue')} label="Integrations"
            active={isActive(ROUTE_DEFS.adminCatalogQueue.path)}
            badge={pendingTickets} />
        </nav>

        {/* User footer */}
        <div className="px-3 py-3 border-t border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-semibold text-slate-600 shrink-0">
              {(userName.slice(0, 1) + (userName.includes(' ') ? userName.split(' ')[1]?.[0] ?? '' : '')).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-900 truncate">{userName} · ReloPass</p>
              <p className="text-[10px] text-slate-400">Admin · superuser</p>
            </div>
            <button className="text-slate-400 hover:text-slate-600">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-slate-200 shrink-0">
          <div className="flex items-center gap-1.5 text-sm text-slate-500">
            <span className="text-slate-400">ReloPass admin</span>
            {title && (
              <>
                <span className="text-slate-300">/</span>
                <span className="text-slate-700 font-medium">{title}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button className="text-slate-400 hover:text-slate-600 transition-colors">
              <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </button>
            <button className="text-slate-400 hover:text-slate-600 transition-colors">
              <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#0b2b43] text-white text-xs font-medium hover:bg-[#0d3456] transition-colors">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Ask ReloPass AI
              <span className="bg-white/20 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px] font-bold">3</span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <div className="px-8 py-7">
            {(title || headerRight) && (
              <div className="flex items-start justify-between mb-6">
                <div>
                  <p className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase mb-1">
                    ReloPass · Internal Superuser Console
                  </p>
                  <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
                  {subtitle && (
                    <p className="text-sm text-slate-500 mt-1 max-w-2xl">{subtitle}</p>
                  )}
                </div>
                {headerRight && <div className="shrink-0 ml-6">{headerRight}</div>}
              </div>
            )}
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

// ── Company switcher (admin-only) ─────────────────────────────────────────────
function logoInitials(name: string): string {
  return name.split(/[\s&]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!).join('').toUpperCase() || '?';
}

function toneFromId(id: string): string {
  let hash = 5381;
  for (let i = 0; i < id.length; i++) hash = ((hash << 5) + hash + id.charCodeAt(i)) | 0;
  const palette = [
    'bg-indigo-600', 'bg-emerald-600', 'bg-amber-600',
    'bg-sky-600', 'bg-rose-600', 'bg-violet-600',
  ];
  return palette[Math.abs(hash) % palette.length]!;
}

const CompanySwitcher: React.FC = () => {
  const { companies, selectedCompany, setSelectedCompanyId, loading, error } = useAdminViewingCompany();
  const navigate = useNavigate();
  // URL is the source of truth for scope. If we're on /admin/companies/:companyId,
  // sync the sidebar selection to that id so the chip reflects what the page
  // is actually showing (and so the dropdown's ✓ marker is accurate).
  const tenantUrl = useMatch('/admin/companies/:companyId/*');
  const urlCompanyId = tenantUrl?.params.companyId ?? null;
  useEffect(() => {
    if (urlCompanyId && companies.some((c) => c.id === urlCompanyId)) {
      setSelectedCompanyId(urlCompanyId);
    }
  }, [urlCompanyId, companies, setSelectedCompanyId]);

  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClickAnywhere = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('click', onClickAnywhere);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('click', onClickAnywhere);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // Pick the visible label + tone from the selected company (fallback for empty / error states).
  const displayName = selectedCompany?.name ?? (loading ? 'Loading…' : error ? 'No companies' : '—');
  const displayId = selectedCompany?.id ?? '';
  const initials = selectedCompany ? logoInitials(selectedCompany.name) : '··';
  const toneClass = displayId ? toneFromId(displayId) : 'bg-slate-400';

  // Filtered list for the dropdown — keeps it usable when there are dozens of tenants.
  const q = filter.trim().toLowerCase();
  const filtered = q
    ? companies.filter((c) => (c.name || '').toLowerCase().includes(q))
    : companies;

  // R1 model: picking a tenant navigates to its detail page rather than
  // applying silent global scope. The URL becomes the canonical "what am I
  // viewing" indicator — see DECISIONS.md for the rationale (rejected
  // alternatives R2 banner-gated scope, R3 server-side query-param scope).
  const handlePick = (c: AdminCompany) => {
    setSelectedCompanyId(c.id);
    setOpen(false);
    setFilter('');
    navigate(`/admin/companies/${c.id}`);
  };

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        disabled={!companies.length}
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <div className={`w-6 h-6 rounded-md ${toneClass} flex items-center justify-center text-[10px] font-bold text-white shrink-0`}>
          {initials}
        </div>
        <span className="text-sm font-medium text-slate-800 flex-1 truncate">{displayName}</span>
        <svg className={`w-3 h-3 text-slate-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 z-30 max-h-[60vh] overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl ring-1 ring-black/5">
          <div className="sticky top-0 z-10 border-b border-slate-100 bg-white p-2">
            <input
              type="search"
              placeholder="Filter tenants…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              autoFocus
              className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          {filtered.length === 0 ? (
            <div className="px-3 py-3 text-xs text-slate-400">No tenants match.</div>
          ) : (
            filtered.map((c) => {
              const isSelected = c.id === selectedCompany?.id;
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => handlePick(c)}
                  className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-slate-50 ${isSelected ? 'bg-indigo-50' : ''}`}
                >
                  <div className={`w-5 h-5 rounded ${toneFromId(c.id)} flex items-center justify-center text-[9px] font-bold text-white shrink-0`}>
                    {logoInitials(c.name)}
                  </div>
                  <span className="flex-1 truncate font-medium text-slate-800">{c.name}</span>
                  {c.country && (
                    <span className="text-[10px] text-slate-400">{c.country}</span>
                  )}
                  {isSelected && (
                    <span className="text-indigo-600 text-[11px]" aria-label="selected">✓</span>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
