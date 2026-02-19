import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Card, Badge, Button, Alert } from '../components/antigravity';
import { dashboardAPI, employeeAPI } from '../api/client';
import type { DashboardResponse } from '../types';
import { buildRoute } from '../navigation/routes';

// Static recommendations for banks, insurances, electricity (no backend yet)
const BANKS = [
  { id: '1', name: 'DBS', services: ['Multi-currency', 'Expats'], contact: 'dbs.com/sg', notes: 'Leading bank for expats in Singapore.' },
  { id: '2', name: 'OCBC', services: ['Savings', 'Mortgages'], contact: 'ocbc.com', notes: 'Full-service retail and wealth management.' },
  { id: '3', name: 'UOB', services: ['Accounts', 'Cards'], contact: 'uob.com.sg', notes: 'Strong regional presence for relocating families.' },
  { id: '4', name: 'Citibank', services: ['Global transfer', 'Priority'], contact: 'citi.com.sg', notes: 'International banking for frequent travelers.' },
];

const INSURANCES = [
  { id: '1', name: 'AIA Singapore', types: ['Health', 'Life'], contact: 'aia.com.sg', notes: 'Comprehensive health and family coverage.' },
  { id: '2', name: 'Prudential', types: ['Medical', 'Travel'], contact: 'prudential.com.sg', notes: 'Expat-focused health and travel plans.' },
  { id: '3', name: 'Allianz', types: ['International health'], contact: 'allianz-care.com', notes: 'Global coverage for relocating employees.' },
  { id: '4', name: 'Cigna Global', types: ['Expat health'], contact: 'cignaglobal.com', notes: 'Portable coverage across countries.' },
];

const ELECTRICITY = [
  { id: '1', name: 'SP Group', plans: ['Standard', 'Green'], contact: 'spgroup.com.sg', notes: 'Default retailer, open electricity market.' },
  { id: '2', name: 'Tuas Power', plans: ['Fixed', 'Discount'], contact: 'tuaspower.com.sg', notes: 'Competitive rates for residential.' },
  { id: '3', name: 'Geneco', plans: ['Flexi', 'Green'], contact: 'geneco.sg', notes: 'Singapore Power subsidiary, various plans.' },
  { id: '4', name: 'Senoko Energy', plans: ['24-month fix'], contact: 'senokoenergy.com', notes: 'Stable pricing for new arrivals.' },
];

type TabKey = 'housing' | 'schools' | 'movers' | 'banks' | 'insurances' | 'electricity';

const SERVICE_OPTIONS: { id: TabKey; label: string; description: string }[] = [
  { id: 'housing', label: 'Living areas', description: 'Recommended neighbourhoods and housing options' },
  { id: 'schools', label: 'Schools', description: 'International and local school recommendations' },
  { id: 'movers', label: 'Movers', description: 'International relocation and moving companies' },
  { id: 'banks', label: 'Banks', description: 'Banking and account setup for expats' },
  { id: 'insurances', label: 'Insurances', description: 'Health, travel, and life insurance providers' },
  { id: 'electricity', label: 'Electricity', description: 'Utilities and electricity retailers' },
];

export const ProvidersPage: React.FC = () => {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [employeeRecs, setEmployeeRecs] = useState<{ housing: any[]; schools: any[]; movers: any[] } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showQuestionnaire, setShowQuestionnaire] = useState(true);
  const [selectedServices, setSelectedServices] = useState<Set<TabKey>>(new Set(SERVICE_OPTIONS.map((s) => s.id)));
  const [activeTab, setActiveTab] = useState<TabKey>('housing');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const toggleService = (id: TabKey) => {
    setSelectedServices((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setError('');
    try {
      const data = await dashboardAPI.get();
      setDashboard(data);
      setEmployeeRecs(null);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        navigate(buildRoute('landing'));
        return;
      }
      setDashboard(null);
      try {
        const recs = await employeeAPI.getRecommendations();
        if (recs && (recs.housing?.length || recs.schools?.length || recs.movers?.length)) {
          setEmployeeRecs(recs);
          setError('');
        } else {
          setError('Complete your case wizard for personalized recommendations. Showing banks, insurances, and electricity below.');
        }
      } catch {
        setEmployeeRecs(null);
        setError('Complete your case wizard for personalized recommendations. Showing banks, insurances, and electricity below.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const housing = dashboard?.recommendations?.housing ?? employeeRecs?.housing ?? [];
  const schools = dashboard?.recommendations?.schools ?? employeeRecs?.schools ?? [];
  const movers = dashboard?.recommendations?.movers ?? employeeRecs?.movers ?? [];

  const allTabs: { id: TabKey; label: string; count?: number }[] = [
    { id: 'housing', label: 'Living areas', count: housing.length },
    { id: 'schools', label: 'Schools', count: schools.length },
    { id: 'movers', label: 'Movers', count: movers.length },
    { id: 'banks', label: 'Banks', count: BANKS.length },
    { id: 'insurances', label: 'Insurances', count: INSURANCES.length },
    { id: 'electricity', label: 'Electricity', count: ELECTRICITY.length },
  ];
  const tabs = allTabs.filter((t) => selectedServices.has(t.id));

  if (isLoading) {
    return (
      <AppShell title="Service Providers" subtitle="Find recommended partners for your relocation.">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0b2b43] mx-auto mb-4" />
          <p className="text-[#6b7280]">Loading recommendations...</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Service Providers" subtitle="Choose the services you need and browse recommendations.">
      {error && (
        <Alert variant="info" className="mb-6">
          {error}
        </Alert>
      )}

      {showQuestionnaire ? (
        <Card padding="lg" className="mb-8">
          <h2 className="text-xl font-semibold text-[#0b2b43] mb-2">Which services do you need?</h2>
          <p className="text-sm text-[#6b7280] mb-6">
            Select the services you want to explore. We'll show you recommended providers for each category.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {SERVICE_OPTIONS.map((opt) => (
              <label
                key={opt.id}
                className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
                  selectedServices.has(opt.id) ? 'border-[#0b2b43] bg-[#eef4f8]' : 'border-[#e2e8f0] hover:border-[#94a3b8]'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedServices.has(opt.id)}
                  onChange={() => toggleService(opt.id)}
                  className="mt-1 h-4 w-4 rounded border-[#e2e8f0] text-[#0b2b43]"
                />
                <div>
                  <div className="font-medium text-[#0b2b43]">{opt.label}</div>
                  <div className="text-sm text-[#6b7280]">{opt.description}</div>
                </div>
              </label>
            ))}
          </div>
          <Button
            className="mt-6"
            onClick={() => {
              const first = SERVICE_OPTIONS.find((o) => selectedServices.has(o.id))?.id ?? 'housing';
              setActiveTab(first);
              setShowQuestionnaire(false);
            }}
            disabled={selectedServices.size === 0}
          >
            Show recommendations
          </Button>
        </Card>
      ) : (
        <>
          <div className="mb-4 flex items-center justify-between">
            <button
              onClick={() => setShowQuestionnaire(true)}
              className="text-sm text-[#0b2b43] hover:underline"
            >
              ← Change service selection
            </button>
          </div>
          <div className="flex flex-wrap gap-2 mb-8 border-b border-[#e2e8f0] pb-4">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-[#0b2b43] text-white'
                    : 'bg-white border border-[#e2e8f0] text-[#4b5563] hover:border-[#0b2b43] hover:text-[#0b2b43]'
                }`}
              >
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="ml-1.5 text-xs opacity-80">({tab.count})</span>
                )}
              </button>
            ))}
          </div>

          <div className="space-y-6">
        {activeTab === 'housing' && (
          <Section title="Recommended areas to live">
            {housing.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {housing.slice(0, 8).map((h) => (
                  <ProviderCard key={h.id}>
                    <h3 className="font-semibold text-[#0b2b43]">{h.name}</h3>
                    <p className="text-sm text-[#6b7280]">{h.area}</p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      <Badge variant="neutral" size="sm">{h.bedrooms} beds</Badge>
                      {h.furnished && <Badge variant="info" size="sm">Furnished</Badge>}
                      {h.nearMRT && <Badge variant="success" size="sm">Near MRT</Badge>}
                    </div>
                    <p className="text-sm text-[#4b5563] mt-2">SGD {h.estMonthlySGDMin.toLocaleString()}–{h.estMonthlySGDMax.toLocaleString()}/mo</p>
                    <p className="text-sm italic text-[#6b7280] mt-1">{h.rationale}</p>
                    <p className="text-sm text-[#374151] mt-1">{h.notes}</p>
                  </ProviderCard>
                ))}
              </div>
            ) : (
              <EmptyState message="Complete your relocation wizard and housing preferences for personalized area recommendations." />
            )}
            </Section>
          )}

          {activeTab === 'schools' && (
          <Section title="School recommendations">
            {schools.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {schools.slice(0, 8).map((s) => (
                  <ProviderCard key={s.id}>
                    <h3 className="font-semibold text-[#0b2b43]">{s.name}</h3>
                    <p className="text-sm text-[#6b7280]">{s.area}</p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {s.curriculumTags.map((t) => (
                        <Badge key={t} variant="info" size="sm">{t}</Badge>
                      ))}
                      <Badge variant="neutral" size="sm">{s.ageRange}</Badge>
                    </div>
                    <p className="text-sm text-[#4b5563] mt-2">SGD {s.estAnnualSGDMin.toLocaleString()}–{s.estAnnualSGDMax.toLocaleString()}/year</p>
                    <p className="text-sm italic text-[#6b7280] mt-1">{s.rationale}</p>
                    <p className="text-sm text-[#374151] mt-1">{s.notes}</p>
                  </ProviderCard>
                ))}
              </div>
            ) : (
              <EmptyState message="Add children and school preferences in your wizard for school recommendations." />
            )}
          </Section>
        )}

        {activeTab === 'movers' && (
          <Section title="Mover recommendations">
            {movers.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {movers.map((m) => (
                  <ProviderCard key={m.id}>
                    <h3 className="font-semibold text-[#0b2b43]">{m.name}</h3>
                    <p className="text-sm italic text-[#6b7280]">{m.rationale}</p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {m.serviceTags.map((t) => (
                        <Badge key={t} variant="success" size="sm">{t}</Badge>
                      ))}
                    </div>
                    <p className="text-sm text-[#374151] mt-2">{m.notes}</p>
                    <div className="mt-2 p-2 bg-[#f8fafc] rounded text-xs">
                      <strong>RFQ template:</strong> {m.rfqTemplate}
                    </div>
                    <Button size="sm" className="mt-3">{m.nextAction}</Button>
                  </ProviderCard>
                ))}
              </div>
            ) : (
              <EmptyState message="Complete mover preferences in your wizard for personalized mover recommendations." />
            )}
          </Section>
        )}

        {activeTab === 'banks' && (
          <Section title="Bank contacts">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {BANKS.map((b) => (
                <ProviderCard key={b.id}>
                  <h3 className="font-semibold text-[#0b2b43]">{b.name}</h3>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {b.services.map((s) => (
                      <Badge key={s} variant="info" size="sm">{s}</Badge>
                    ))}
                  </div>
                  <p className="text-sm text-[#374151] mt-2">{b.notes}</p>
                  <p className="text-sm text-[#0b2b43] mt-1">
                    <a href={`https://${b.contact}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      {b.contact}
                    </a>
                  </p>
                </ProviderCard>
              ))}
            </div>
          </Section>
        )}

        {activeTab === 'insurances' && (
          <Section title="Insurance contacts">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {INSURANCES.map((i) => (
                <ProviderCard key={i.id}>
                  <h3 className="font-semibold text-[#0b2b43]">{i.name}</h3>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {i.types.map((t) => (
                      <Badge key={t} variant="info" size="sm">{t}</Badge>
                    ))}
                  </div>
                  <p className="text-sm text-[#374151] mt-2">{i.notes}</p>
                  <p className="text-sm text-[#0b2b43] mt-1">
                    <a href={`https://${i.contact}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      {i.contact}
                    </a>
                  </p>
                </ProviderCard>
              ))}
            </div>
          </Section>
        )}

        {activeTab === 'electricity' && (
          <Section title="Electricity providers">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ELECTRICITY.map((e) => (
                <ProviderCard key={e.id}>
                  <h3 className="font-semibold text-[#0b2b43]">{e.name}</h3>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {e.plans.map((p) => (
                      <Badge key={p} variant="neutral" size="sm">{p}</Badge>
                    ))}
                  </div>
                  <p className="text-sm text-[#374151] mt-2">{e.notes}</p>
                  <p className="text-sm text-[#0b2b43] mt-1">
                    <a href={`https://${e.contact}`} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      {e.contact}
                    </a>
                  </p>
                </ProviderCard>
              ))}
            </div>
          </Section>
        )}
      </div>

          <div className="mt-8 pt-6 border-t border-[#e2e8f0]">
            <p className="text-xs text-[#6b7280]">
              Provider listings are for informational purposes. ReloPass does not endorse any specific provider.
            </p>
          </div>
        </>
      )}
    </AppShell>
  );
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-xl font-semibold text-[#0b2b43] mb-4">{title}</h2>
      {children}
    </div>
  );
}

function ProviderCard({ children }: { children: React.ReactNode }) {
  return (
    <Card padding="md" className="hover:shadow-md transition-shadow">
      {children}
    </Card>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <Card padding="lg">
      <div className="text-center py-8">
        <p className="text-[#6b7280]">{message}</p>
        <Button variant="outline" className="mt-4" onClick={() => window.location.href = '/employee/dashboard'}>
          Go to My Case
        </Button>
      </div>
    </Card>
  );
}
