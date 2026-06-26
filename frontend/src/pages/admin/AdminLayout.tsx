import React, { useEffect, useRef, useState } from 'react';
import { useMatch, useNavigate } from 'react-router-dom';
import { Input } from '../../components/antigravity/Input';
import { Button } from '../../components/antigravity/Button';
import { getAuthItem } from '../../utils/demo';
import { useAdminViewingCompany } from '../../features/admin/AdminViewingCompanyContext';
import type { AdminCompany } from '../../types';
import { PlatformShellSidebar } from '../../components/PlatformShellSidebar';

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

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">

      {/* AIQ-397: skip-link for keyboard users — visually hidden until focused. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-[#0b2b43] focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:shadow-lg"
      >
        Skip to main content
      </a>

      <PlatformShellSidebar
        role="ADMIN"
        companySlot={<CompanySwitcher />}
        user={{
          initials: deriveInitials(userName),
          name: `${userName} · ReloPass`,
          role: 'Admin · superuser',
        }}
      />

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
            <Button unstyled aria-label="Download" className="text-slate-400 hover:text-slate-600 transition-colors">
              <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </Button>
            <Button unstyled aria-label="Notifications" className="text-slate-400 hover:text-slate-600 transition-colors">
              <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </Button>
            <Button unstyled className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#0b2b43] text-white text-xs font-medium hover:bg-[#0d3456] transition-colors">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Ask ReloPass AI
              <span className="bg-white/20 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px] font-bold">3</span>
            </Button>
          </div>
        </header>

        {/* Page content */}
        <main id="main-content" className="flex-1 overflow-y-auto">
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
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <div className={`w-6 h-6 rounded-md ${toneClass} flex items-center justify-center text-[10px] font-bold text-white shrink-0`}>
          {initials}
        </div>
        <span className="text-sm font-medium text-slate-800 flex-1 truncate">{displayName}</span>
        <svg className={`w-3 h-3 text-slate-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </Button>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 z-30 max-h-[60vh] overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl ring-1 ring-black/5">
          <div className="sticky top-0 z-10 border-b border-slate-100 bg-white p-2">
            <Input unstyled
              type="search"
              placeholder="Filter tenants…"
              value={filter}
              onChange={(v) => setFilter(v)}
              autoFocus
              className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
          </div>
          {filtered.length === 0 ? (
            <div className="px-3 py-3 text-xs text-slate-400">No tenants match.</div>
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
                    <span className="text-[10px] text-slate-400">{c.country}</span>
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
