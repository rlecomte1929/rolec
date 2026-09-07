import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useMatch, useNavigate } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { Input } from '../../components/antigravity/Input';
import { Button } from '../../components/antigravity/Button';
import { PageHeader } from '../../components/antigravity/PageHeader';
import { getAuthItem } from '../../utils/demo';
import { useAdminViewingCompany } from '../../features/admin/AdminViewingCompanyContext';
import type { AdminCompany } from '../../types';
import { PlatformShellSidebar } from '../../components/PlatformShellSidebar';
import { FeedbackWidget } from '../../components/FeedbackWidget';
import { authAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';

interface Props {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Extra content rendered inline with the page heading (e.g. scope badges). */
  headerRight?: React.ReactNode;
}

// ── Main layout ───────────────────────────────────────────────────────────────

function deriveInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'RP';
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}

export const AdminLayout: React.FC<Props> = ({ title, subtitle, children, headerRight }) => {
  const userName = getAuthItem('relopass_name') ?? 'Romain';
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileNavOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mobileNavOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">

      {/* AIQ-397: skip-link for keyboard users — visually hidden until focused. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-[#0b2b43] focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:shadow-lg"
      >
        Skip to main content
      </a>

      {mobileNavOpen && (
        // eslint-disable-next-line local/no-clickable-div -- presentational mouse-dismiss overlay
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          aria-hidden="true"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      <div
        className={`fixed inset-y-0 left-0 z-50 flex transition-transform duration-200 ease-out md:static md:z-auto md:translate-x-0 md:transition-none ${
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
      {/* eslint-disable jsx-a11y/aria-role */}
      {/* `role` is a PlatformShellSidebar component prop (SidebarRole enum), not an ARIA role */}
      <PlatformShellSidebar
        role="ADMIN"
        companySlot={<CompanySwitcher />}
        user={{
          initials: deriveInitials(userName),
          name: `${userName} · ReloPass`,
          role: 'Admin · superuser',
        }}
      />
      {/* eslint-enable jsx-a11y/aria-role */}
      </div>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-slate-200 shrink-0">
          <div className="flex items-center gap-1.5 text-sm text-slate-500">
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              aria-label="Open navigation menu"
              aria-expanded={mobileNavOpen}
              className="md:hidden grid h-11 w-11 shrink-0 place-items-center rounded-md text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/30"
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>
            <span className="text-slate-500">ReloPass admin</span>
            {title && (
              <>
                <span className="text-slate-500">/</span>
                <span className="text-slate-700 font-medium">{title}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* SHELL-1 + founder cockpit: removed non-functional Notifications,
               Download, and Ask ReloPass AI — they had no handlers. */}
            <AdminAccountMenu name={userName} initials={deriveInitials(userName)} />
          </div>
        </header>

        {/* Page content — SHELL-1: capped + centered (wider than Employee/HR's 7xl,
           per the dense admin tables) instead of full-bleed. */}
        <main id="main-content" className="flex-1 overflow-y-auto">
          <div className="px-4 py-6 md:px-8 md:py-7 max-w-[1600px] mx-auto">
            {(title || headerRight) && (
              <PageHeader
                eyebrow="ReloPass · Founder console"
                title={title ?? ''}
                subtitle={subtitle}
                actions={headerRight}
              />
            )}
            {children}
          </div>
        </main>
      </div>

      {/* Floating feedback widget — same one employee/HR get via AppShell, so admins can
          report bugs / ideas from inside the console. Submits to the same feedback stream
          the Feedback tab reads. */}
      <FeedbackWidget userId={getAuthItem('relopass_user_id')} />
    </div>
  );
};

// ── Account menu (top-right sign-out) ─────────────────────────────────────────
// AIQ-1442: gives admins the same top-right logout affordance the employee/HR shell
// (AppShell) already has. Reuses the canonical logout path — authAPI.logout() then a
// hard redirect to the login page — identical to AppShell's LogoutButton and the
// sidebar footer's handleSignOut, so there is one source of truth for sign-out.
const AdminAccountMenu: React.FC<{ name: string; initials: string }> = ({ name, initials }) => {
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
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

  const handleSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await authAPI.logout();
      window.location.replace(buildRoute('login'));
    } catch {
      setSigningOut(false);
    }
  };

  return (
    <div ref={wrapperRef} className="relative">
      <Button unstyled
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={() => setOpen((o) => !o)}
        className="flex min-h-11 items-center gap-1.5 pl-1 pr-1.5 py-1 rounded-lg hover:bg-slate-50 transition-colors"
      >
        <div className="w-7 h-7 rounded-full bg-[#0b2b43] flex items-center justify-center text-[11px] font-bold text-white shrink-0">
          {initials}
        </div>
        <svg className={`w-3 h-3 text-slate-500 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </Button>

      {open && (
        <div role="menu" className="absolute right-0 top-full mt-1 z-30 w-52 rounded-lg border border-slate-200 bg-white shadow-xl ring-1 ring-black/5">
          <div className="border-b border-slate-100 px-3 py-2">
            <p className="text-sm font-medium text-slate-800 truncate">{name}</p>
            <p className="text-[11px] text-slate-500">Admin · superuser</p>
          </div>
          <Button unstyled
            type="button"
            role="menuitem"
            onClick={handleSignOut}
            disabled={signingOut}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            <svg className="w-4 h-4 text-slate-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            {signingOut ? 'Signing out…' : 'Sign out'}
          </Button>
        </div>
      )}
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
    'bg-accent-600', 'bg-emerald-600', 'bg-amber-600',
    'bg-sky-600', 'bg-rose-600', 'bg-accent-600',
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
      <Button unstyled
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        disabled={!companies.length}
        className="flex min-h-11 w-full items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <div className={`w-6 h-6 rounded-md ${toneClass} flex items-center justify-center text-[10px] font-bold text-white shrink-0`}>
          {initials}
        </div>
        <span className="text-sm font-medium text-slate-800 flex-1 truncate">{displayName}</span>
        <svg className={`w-3 h-3 text-slate-500 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </Button>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 z-30 max-h-[60vh] overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl ring-1 ring-black/5">
          <div className="sticky top-0 z-10 border-b border-slate-100 bg-white p-2">
            {/* eslint-disable jsx-a11y/no-autofocus */}
            {/* tenant switcher dropdown: focus filter input when popover opens for keyboard users */}
            <Input unstyled
              type="search"
              placeholder="Filter tenants…"
              value={filter}
              onChange={(v) => setFilter(v)}
              autoFocus
              className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
            {/* eslint-enable jsx-a11y/no-autofocus */}
          </div>
          {filtered.length === 0 ? (
            <div className="px-3 py-3 text-xs text-slate-500">No tenants match.</div>
          ) : (
            filtered.map((c) => {
              const isSelected = c.id === selectedCompany?.id;
              return (
                <Button unstyled
                  key={c.id}
                  type="button"
                  onClick={() => handlePick(c)}
                  className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-slate-50 ${isSelected ? 'bg-accent-50' : ''}`}
                >
                  <div className={`w-5 h-5 rounded ${toneFromId(c.id)} flex items-center justify-center text-[9px] font-bold text-white shrink-0`}>
                    {logoInitials(c.name)}
                  </div>
                  <span className="flex-1 truncate font-medium text-slate-800">{c.name}</span>
                  {c.country && (
                    <span className="text-[10px] text-slate-500">{c.country}</span>
                  )}
                  {isSelected && (
                    <span className="text-accent-600 text-[11px]" aria-label="selected">✓</span>
                  )}
                </Button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
