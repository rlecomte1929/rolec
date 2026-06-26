/**
 * [NAV-SP-1] Service Providers — grouped surface with three sub-tabs.
 *
 * Re-homes the two existing HR vendor surfaces under one parent:
 *   • Dashboard        — placeholder slot, filled by [NAV-SP-2].
 *   • Vendor Management — embeds the existing HrVendorCuration page unchanged.
 *   • Provider Status   — embeds the existing ProviderGridV2Page unchanged.
 *
 * Mirrors the in-page-tabs container pattern from HrPolicy.tsx: one AppShell +
 * a ?tab=-driven tab bar, with each shell-owning child rendered `embedded` so
 * we don't double-nest the platform shell. The standalone /hr/vendor-curation
 * and /hr/provider-grid routes are left intact for backward compatibility.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Button, Card, Badge } from '../components/antigravity';
import { VendorPerformancePage } from '../features/platform-v2/vendor-performance/VendorPerformancePage';
import {
  getHrNotificationCounts,
  listEmployeeDemand,
  type HrNotificationCounts,
  type EmployeeDemandRow,
} from '../api/hrCatalog';
import { HrVendorCuration } from './HrVendorCuration';

type ServiceTab = 'dashboard' | 'vendor' | 'providers';

const TABS: { key: ServiceTab; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'vendor', label: 'Vendor Management' },
  { key: 'providers', label: 'Vendor Performance' },
];

export const HrServiceProvidersPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const raw = searchParams.get('tab');
  const activeTab: ServiceTab =
    raw === 'vendor' || raw === 'providers' ? raw : 'dashboard';

  const setTab = (tab: ServiceTab) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', tab);
    setSearchParams(next, { replace: true });
  };

  return (
    <AppShell
      section="HR Operations"
      title="Service Providers"
      subtitle="Curate the providers your employees see and track their coordination status."
    >
      {/* Tab bar */}
      <div className="flex gap-1 mb-4 border-b border-slate-200">
        {TABS.map((t) => (
          <ServiceTabButton key={t.key} active={activeTab === t.key} onClick={() => setTab(t.key)}>
            {t.label}
          </ServiceTabButton>
        ))}
      </div>

      {activeTab === 'vendor' ? (
        <HrVendorCuration embedded />
      ) : activeTab === 'providers' ? (
        <VendorPerformancePage embedded />
      ) : (
        <ServiceProvidersDashboard
          onAddVendor={() => setTab('vendor')}
          onReviewProviders={() => setTab('providers')}
        />
      )}
    </AppShell>
  );
};

function ServiceTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      unstyled
      type="button"
      onClick={onClick}
      className={[
        'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
        active
          ? 'border-accent-600 text-accent-700'
          : 'border-transparent text-slate-500 hover:text-slate-700',
      ].join(' ')}
    >
      {children}
    </Button>
  );
}

/** [NAV-SP-2] Executive vendor-health view. Composes the existing company-scoped
 *  catalog endpoints (notification-counts + employee-demand) — no new CRUD.
 *  Note: per-category "active vendors by category", health breakdown, and a
 *  recent-activity feed need a curation/status aggregate that isn't exposed
 *  company-wide today (getCurationView is per category × city); those widgets are
 *  a follow-up. The coverage-gap view below is the core executive signal. */
function Stat({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'amber' }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-1 text-[26px] font-semibold leading-none tabular-nums ${tone === 'amber' ? 'text-amber-700' : 'text-slate-900'}`}>
        {value}
      </div>
    </div>
  );
}

function ServiceProvidersDashboard({
  onAddVendor,
  onReviewProviders,
}: {
  onAddVendor: () => void;
  onReviewProviders: () => void;
}) {
  const [counts, setCounts] = useState<HrNotificationCounts | null>(null);
  const [demand, setDemand] = useState<EmployeeDemandRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ctrl = new AbortController();
    void Promise.allSettled([getHrNotificationCounts(), listEmployeeDemand(ctrl.signal)]).then(
      ([c, d]) => {
        if (c.status === 'fulfilled') setCounts(c.value);
        if (d.status === 'fulfilled') setDemand(d.value);
        setLoading(false);
      },
    );
    return () => ctrl.abort();
  }, []);

  // Coverage gaps = unmet employee demand, grouped by service category.
  const gapsByCategory = useMemo(() => {
    const m = new Map<string, { category: string; total: number; rows: EmployeeDemandRow[] }>();
    for (const r of demand) {
      const cur = m.get(r.category) ?? { category: r.category, total: 0, rows: [] };
      cur.total += r.demand_count;
      cur.rows.push(r);
      m.set(r.category, cur);
    }
    return [...m.values()].sort((a, b) => b.total - a.total);
  }, [demand]);

  if (loading && !counts) {
    return <div className="py-8 text-sm text-slate-500">Loading dashboard…</div>;
  }

  return (
    <div className="space-y-5">
      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Employees waiting" value={counts?.employees_waiting ?? 0} tone={counts?.employees_waiting ? 'amber' : 'default'} />
        <Stat label="Destinations with demand" value={counts?.destinations_with_demand ?? 0} />
        <Stat label="Pending admin tickets" value={counts?.pending_admin_tickets ?? 0} tone={counts?.pending_admin_tickets ? 'amber' : 'default'} />
      </div>

      {/* Coverage gaps */}
      <Card padding="none" className="overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-[#0b2b43]">Coverage gaps</h3>
            <p className="text-xs text-slate-500">
              Service categories your employees are requesting, by destination — fill these in Vendor Management.
            </p>
          </div>
          <Badge variant={gapsByCategory.length ? 'warning' : 'success'} size="sm">
            {gapsByCategory.length} categor{gapsByCategory.length === 1 ? 'y' : 'ies'}
          </Badge>
        </div>
        {gapsByCategory.length === 0 ? (
          <div className="px-4 py-4 text-sm text-slate-500">No open coverage gaps — every requested category has a destination match.</div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {gapsByCategory.slice(0, 8).map((g) => (
              <li key={g.category} className="px-4 py-2.5">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium capitalize text-[#0b2b43]">{g.category.replace(/_/g, ' ')}</span>
                  <span className="tabular-nums text-xs text-slate-500">{g.total} employee{g.total === 1 ? '' : 's'} waiting</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {g.rows.slice(0, 4).map((r) => (
                    <Badge key={r.id} variant="neutral" size="sm">
                      {[r.destination_city, r.destination_country].filter(Boolean).join(', ') || 'Unspecified'} · {r.demand_count}
                    </Badge>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Quick actions */}
      <div className="flex flex-wrap gap-2">
        <Button onClick={onAddVendor}>Add / manage vendors →</Button>
        <Button variant="outline" onClick={onReviewProviders}>Track provider status →</Button>
      </div>
    </div>
  );
}

export default HrServiceProvidersPage;
