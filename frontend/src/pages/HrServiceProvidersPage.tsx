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
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Button, Card } from '../components/antigravity';
import { HrVendorCuration } from './HrVendorCuration';
import { ProviderGridV2Page } from '../features/platform-v2/provider-grid/ProviderGridV2Page';

type ServiceTab = 'dashboard' | 'vendor' | 'providers';

const TABS: { key: ServiceTab; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'vendor', label: 'Vendor Management' },
  { key: 'providers', label: 'Provider Status' },
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
        <ProviderGridV2Page embedded />
      ) : (
        <ServiceProvidersDashboardPlaceholder />
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

/** Placeholder until [NAV-SP-2] fills the Dashboard tab. */
function ServiceProvidersDashboardPlaceholder() {
  return (
    <Card padding="lg" className="text-center">
      <h2 className="text-lg font-semibold text-[#0b2b43]">Service Providers dashboard</h2>
      <p className="mt-2 max-w-xl mx-auto text-sm text-slate-500">
        A consolidated view of vendor selections and provider coordination is coming soon. In the
        meantime, use the <strong>Vendor Management</strong> tab to choose the providers your
        employees see, and <strong>Provider Status</strong> to track their progress across active
        relocations.
      </p>
    </Card>
  );
}

export default HrServiceProvidersPage;
