import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card, Input } from '../components/antigravity';
import { employeeAPI } from '../api/client';
import { buildRoute } from '../navigation/routes';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';

type ServiceItem = {
  key: string;
  label: string;
  description: string;
  category: string;
};

const SERVICE_CATALOG: ServiceItem[] = [
  { key: 'temporary_housing', label: 'Temporary housing', description: 'Short-term stay support on arrival.', category: 'housing' },
  { key: 'long_term_rental', label: 'Long-term rental support', description: 'Help finding longer-term housing.', category: 'housing' },
  { key: 'school_search', label: 'School search', description: 'Guidance on school selection and enrollment.', category: 'schools' },
  { key: 'visa_support', label: 'Visa support', description: 'Immigration and visa documentation assistance.', category: 'immigration' },
  { key: 'tax_consult', label: 'Tax consultation', description: 'High-level tax onboarding consultation.', category: 'tax' },
  { key: 'movers', label: 'Movers', description: 'Moving logistics and shipment coordination.', category: 'moving' },
  { key: 'settling_in', label: 'Settling-in services', description: 'Bank, SIM, healthcare registration support.', category: 'settling_in' },
];

type ServiceState = {
  selected: boolean;
  estimated_cost: string;
};

export const ProvidersPage: React.FC = () => {
  const { assignmentId, isLoading: assignmentLoading } = useEmployeeAssignment();
  const [services, setServices] = useState<Record<string, ServiceState>>({});
  const [policy, setPolicy] = useState<{ currency: string; caps: Record<string, number>; total_cap?: number | null } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    if (assignmentLoading) return;
    if (!assignmentId) {
      setIsLoading(false);
      return;
    }
    const load = async () => {
      setIsLoading(true);
      setMessage('');
      try {
        const [serviceRes, policyRes] = await Promise.all([
          employeeAPI.getAssignmentServices(assignmentId),
          employeeAPI.getPolicyBudget(assignmentId),
        ]);
        const baseState: Record<string, ServiceState> = {};
        SERVICE_CATALOG.forEach((svc) => {
          baseState[svc.key] = { selected: false, estimated_cost: '' };
        });
        serviceRes.services?.forEach((row) => {
          baseState[row.service_key] = {
            selected: Boolean(row.selected),
            estimated_cost: row.estimated_cost !== null && row.estimated_cost !== undefined ? String(row.estimated_cost) : '',
          };
        });
        setServices(baseState);
        setPolicy(policyRes);
      } catch (err: any) {
        if (err?.response?.status === 401) {
          navigate(buildRoute('landing'));
          return;
        }
        setMessage('Unable to load services. Please refresh and try again.');
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [assignmentId, assignmentLoading, navigate]);

  const totals = useMemo(() => {
    const byCategory: Record<string, number> = {};
    let total = 0;
    SERVICE_CATALOG.forEach((svc) => {
      const state = services[svc.key];
      if (!state?.selected) return;
      const cost = Number(state.estimated_cost);
      if (!Number.isFinite(cost)) return;
      byCategory[svc.category] = (byCategory[svc.category] || 0) + cost;
      total += cost;
    });
    return { byCategory, total };
  }, [services]);

  const handleToggle = (key: string) => {
    setServices((prev) => ({
      ...prev,
      [key]: { selected: !prev[key]?.selected, estimated_cost: prev[key]?.estimated_cost || '' },
    }));
  };

  const handleCostChange = (key: string, value: string) => {
    setServices((prev) => ({
      ...prev,
      [key]: { selected: prev[key]?.selected || false, estimated_cost: value },
    }));
  };

  const handleSave = async () => {
    if (!assignmentId) return;
    setIsSaving(true);
    setMessage('');
    try {
      const payload = SERVICE_CATALOG.map((svc) => {
        const state = services[svc.key] || { selected: false, estimated_cost: '' };
        return {
          service_key: svc.key,
          category: svc.category,
          selected: state.selected,
          estimated_cost: state.estimated_cost ? Number(state.estimated_cost) : null,
          currency: policy?.currency || 'EUR',
        };
      });
      await employeeAPI.saveAssignmentServices(assignmentId, payload);
      setMessage('Saved services successfully.');
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Unable to save services. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  if (assignmentLoading || isLoading) {
    return (
      <AppShell title="Services" subtitle="Choose the services you need for your relocation.">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0b2b43] mx-auto mb-4" />
          <p className="text-[#6b7280]">Loading services...</p>
        </div>
      </AppShell>
    );
  }

  if (!assignmentId) {
    return (
      <AppShell title="Services" subtitle="Choose the services you need for your relocation.">
        <Alert variant="info" className="mb-6">
          Complete your case first to unlock services selection.
        </Alert>
        <Button onClick={() => navigate(buildRoute('employeeDashboard'))}>Back to Dashboard</Button>
      </AppShell>
    );
  }

  return (
    <AppShell title="Services" subtitle="Choose the services you need and compare against HR policy budgets.">
      {message && (
        <Alert variant={message.includes('Saved') ? 'success' : 'error'} className="mb-6">
          {message}
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <Card padding="lg">
            <div className="text-lg font-semibold text-[#0b2b43] mb-2">Select services</div>
            <div className="space-y-4">
              {SERVICE_CATALOG.map((svc) => {
                const state = services[svc.key] || { selected: false, estimated_cost: '' };
                const cap = policy?.caps?.[svc.category];
                return (
                  <div key={svc.key} className="border border-[#e2e8f0] rounded-lg p-4 space-y-2">
                    <div className="flex items-start justify-between gap-4">
                      <label className="flex items-start gap-3 text-sm text-[#0b2b43]">
                        <input
                          type="checkbox"
                          checked={state.selected}
                          onChange={() => handleToggle(svc.key)}
                        />
                        <div>
                          <div className="font-semibold">{svc.label}</div>
                          <div className="text-xs text-[#6b7280]">{svc.description}</div>
                        </div>
                      </label>
                      <Badge variant="neutral">{svc.category.replace('_', ' ')}</Badge>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-sm text-[#6b7280]">
                      <Input
                        type="number"
                        label="Estimated cost"
                        value={state.estimated_cost}
                        onChange={(value) => handleCostChange(svc.key, value)}
                        placeholder="0"
                        fullWidth
                      />
                      <div className="text-xs">
                        Policy cap: {cap ? `${policy?.currency} ${cap}` : 'policy not provided'}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card padding="lg">
            <div className="text-lg font-semibold text-[#0b2b43] mb-2">Quotes (Coming soon)</div>
            <div className="text-sm text-[#6b7280] mb-4">
              Next we will let you request quotes from providers, compare offers, and update your budget.
            </div>
            <Button variant="outline" disabled>
              Request quotes (coming soon)
            </Button>
          </Card>
        </div>

        <div className="space-y-4">
          <Card padding="lg">
            <div className="text-lg font-semibold text-[#0b2b43] mb-2">Budget summary</div>
            <div className="space-y-3 text-sm">
              {Object.entries(totals.byCategory).length === 0 && (
                <div className="text-[#6b7280]">No services selected yet.</div>
              )}
              {Object.entries(totals.byCategory).map(([category, total]) => {
                const cap = policy?.caps?.[category];
                const within = cap ? total <= cap : null;
                return (
                  <div key={category} className="flex items-center justify-between">
                    <div className="text-[#0b2b43] capitalize">{category.replace('_', ' ')}</div>
                    <div className="text-right">
                      <div>{policy?.currency || 'EUR'} {total.toFixed(0)}</div>
                      {cap ? (
                        <div className={`text-xs ${within ? 'text-emerald-600' : 'text-rose-600'}`}>
                          {within ? 'Within policy' : `Exceeding by ${policy?.currency} ${(total - cap).toFixed(0)}`}
                        </div>
                      ) : (
                        <div className="text-xs text-[#6b7280]">Policy not provided</div>
                      )}
                    </div>
                  </div>
                );
              })}
              <div className="border-t border-[#e2e8f0] pt-3 flex items-center justify-between">
                <div className="font-semibold text-[#0b2b43]">Total</div>
                <div className="text-right">
                  <div className="font-semibold">{policy?.currency || 'EUR'} {totals.total.toFixed(0)}</div>
                </div>
              </div>
            </div>
          </Card>

          <Card padding="lg">
            <div className="text-sm text-[#6b7280] mb-4">
              Save your service selections so HR can review budget alignment.
            </div>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? 'Saving…' : 'Save services'}
            </Button>
          </Card>
        </div>
      </div>
    </AppShell>
  );
};
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Card, Badge, Button, Alert } from '../components/antigravity';
import { dashboardAPI, employeeAPI } from '../api/client';
import type { DashboardResponse } from '../types';
import { buildRoute } from '../navigation/routes';
import { ProvidersCriteriaWizard, profileToWizardAnswers } from '../features/recommendations/ProvidersCriteriaWizard';
import { RecommendationResults } from '../features/recommendations/RecommendationResults';
import { PackageSummary } from '../features/recommendations/PackageSummary';
import { EmployeePolicyView } from '../features/policy/EmployeePolicyView';
import { TrustBlock } from '../features/services/TrustBlock';
import { ServiceGroupSection } from '../features/services/ServiceGroupSection';
import { StickyContinueBar } from '../features/services/StickyContinueBar';
import { SERVICE_CONFIG, CATEGORY_LABELS } from '../features/services/serviceConfig';
import type { RecommendationResponse } from '../features/recommendations/types';

type TabKey = 'housing' | 'schools' | 'movers' | 'banks' | 'insurances' | 'electricity';

const WIZARD_KEYS: Set<string> = new Set(['housing', 'schools', 'movers', 'banks', 'insurances', 'electricity']);

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

export const ProvidersPage: React.FC = () => {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [employeeRecs, setEmployeeRecs] = useState<{ housing: any[]; schools: any[]; movers: any[] } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  // Wizard-first flow: always start with service selection, then criteria wizard, then results
  const [flowStep, setFlowStep] = useState<'select' | 'wizard' | 'results' | 'summary'>('select');
  const [engineResults, setEngineResults] = useState<Record<string, RecommendationResponse> | null>(null);
  const [selectedPackage, setSelectedPackage] = useState<Map<string, string>>(new Map());
  const [wizardInitialAnswers, setWizardInitialAnswers] = useState<Record<string, unknown>>({});
  const enabledKeys = SERVICE_CONFIG.filter((s) => s.enabled).map((s) => s.key);
  const [selectedServices, setSelectedServices] = useState<Set<string>>(new Set(enabledKeys));
  const [activeTab, setActiveTab] = useState<TabKey>('housing');
  const [error, setError] = useState('');
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleStartOver = () => {
    setEngineResults(null);
    setFlowStep('select');
  };

  const startWizard = async () => {
    setWizardInitialAnswers({});
    try {
      const res = await employeeAPI.getCurrentAssignment();
      let profileAnswers: Record<string, unknown> = {};
      let policyCriteria: Record<string, unknown> = {};
      if (res?.assignment?.id) {
        const [journey, applicable] = await Promise.all([
          employeeAPI.getNextQuestion(res.assignment.id),
          employeeAPI.getApplicablePolicy(res.assignment.id),
        ]);
        const profile = (journey as { profile?: Record<string, unknown> })?.profile;
        if (profile && typeof profile === 'object') {
          profileAnswers = profileToWizardAnswers(profile as Record<string, unknown>);
        }
        if (applicable?.wizardCriteria && typeof applicable.wizardCriteria === 'object') {
          policyCriteria = applicable.wizardCriteria as Record<string, unknown>;
        }
      }
      const merged = { ...profileAnswers, ...policyCriteria };
      setWizardInitialAnswers(Object.keys(merged).length > 0 ? merged : {});
    } catch {
      // Use defaults if no assignment or API error
    }
    setFlowStep('wizard');
  };

  const toggleService = (key: string) => {
    setSelectedServices((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const wizardSelectedServices = new Set([...selectedServices].filter((k) => WIZARD_KEYS.has(k))) as Set<TabKey>;

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setError('');
    try {
      const [data, assignmentRes] = await Promise.all([
        dashboardAPI.get(),
        employeeAPI.getCurrentAssignment().catch(() => null),
      ]);
      setDashboard(data);
      setEmployeeRecs(null);
      setAssignmentId(assignmentRes?.assignment?.id ?? null);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        navigate(buildRoute('landing'));
        return;
      }
      setDashboard(null);
      try {
        const [recs, assignRes] = await Promise.all([
          employeeAPI.getRecommendations(),
          employeeAPI.getCurrentAssignment().catch(() => null),
        ]);
        setAssignmentId(assignRes?.assignment?.id ?? null);
        if (recs && (recs.housing?.length || recs.schools?.length || recs.movers?.length)) {
          setEmployeeRecs(recs);
          setError('');
        } else {
          setError('Select services below and answer a few questions to get personalized recommendations. Banks, insurances, and electricity are also available.');
        }
      } catch {
        setEmployeeRecs(null);
        setError('Select services below and answer a few questions to get personalized recommendations. Banks, insurances, and electricity are also available.');
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
  const tabs = allTabs.filter((t) => wizardSelectedServices.has(t.id));

  if (isLoading) {
    return (
      <AppShell title="Services" subtitle="Find recommended partners for your relocation.">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0b2b43] mx-auto mb-4" />
          <p className="text-[#6b7280]">Loading recommendations...</p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Services" subtitle="Choose the services you need and browse recommendations.">
      {error && (
        <Alert variant="info" className="mb-6">
          {error}
        </Alert>
      )}

      {flowStep === 'select' ? (
        <>
          {assignmentId && (
            <div className="mb-6">
              <EmployeePolicyView assignmentId={assignmentId} compact />
            </div>
          )}
          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-[#0b2b43] mb-2">Your relocation plan</h1>
            <p className="text-[#6b7280] mb-1">
              Select the areas where you need support — we'll build a clear plan so nothing falls through the cracks.
            </p>
            <p className="text-sm text-[#94a3b8]">~3 min to complete</p>
          </div>
          <TrustBlock className="mb-8" />
          <ServiceGroupSection
            group="before"
            items={SERVICE_CONFIG.filter((s) => s.group === 'before')}
            selectedKeys={selectedServices}
            onToggle={toggleService}
          />
          <ServiceGroupSection
            group="arrival"
            items={SERVICE_CONFIG.filter((s) => s.group === 'arrival')}
            selectedKeys={selectedServices}
            onToggle={toggleService}
          />
          <ServiceGroupSection
            group="settle"
            items={SERVICE_CONFIG.filter((s) => s.group === 'settle')}
            selectedKeys={selectedServices}
            onToggle={toggleService}
          />
          <StickyContinueBar
            selectedCount={wizardSelectedServices.size}
            onContinue={startWizard}
          />
        </>
      ) : flowStep === 'wizard' ? (
        <ProvidersCriteriaWizard
          selectedServices={wizardSelectedServices}
          initialAnswers={wizardInitialAnswers}
          onComplete={(results: Record<string, RecommendationResponse>) => {
            setEngineResults(results);
            setSelectedPackage(new Map());
            setFlowStep('results');
            setError('');
          }}
          onBack={handleStartOver}
        />
      ) : flowStep === 'results' && engineResults ? (
        <RecommendationResults
          results={engineResults}
          categoryLabels={CATEGORY_LABELS}
          selectedPackage={selectedPackage}
          onSelectedPackageChange={setSelectedPackage}
          onStartOver={handleStartOver}
          onViewSummary={() => setFlowStep('summary')}
        />
      ) : flowStep === 'summary' && engineResults ? (
        <PackageSummary
          results={engineResults}
          selectedPackage={selectedPackage}
          categoryLabels={CATEGORY_LABELS}
          onBack={() => setFlowStep('results')}
          onStartOver={handleStartOver}
        />
      ) : (
        <>
          <Card padding="lg" className="mb-6">
            <p className="text-[#4b5563] mb-4">Get personalized recommendations by answering a few questions about your preferences.</p>
            <Button onClick={startWizard} disabled={wizardSelectedServices.size === 0}>
              Start service preferences wizard
            </Button>
          </Card>
          <div className="mb-4 flex items-center justify-between">
            <button
              onClick={handleStartOver}
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
              <EmptyState message="Complete your relocation wizard and housing preferences for personalized area recommendations." onStartWizard={startWizard} />
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
                      {s.curriculumTags.map((t: string) => (
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
              <EmptyState message="Add children and school preferences in your wizard for school recommendations." onStartWizard={startWizard} />
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
                      {m.serviceTags.map((t: string) => (
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
              <EmptyState message="Complete mover preferences in your wizard for personalized mover recommendations." onStartWizard={startWizard} />
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

function EmptyState({ message, onStartWizard }: { message: string; onStartWizard?: () => void }) {
  return (
    <Card padding="lg">
      <div className="text-center py-8">
        <p className="text-[#6b7280]">{message}</p>
        <div className="flex flex-wrap justify-center gap-3 mt-4">
          {onStartWizard && (
            <Button onClick={onStartWizard}>
              Start Service Wizard
            </Button>
          )}
          <Button variant="outline" onClick={() => { window.location.href = '/employee/journey'; }}>
            Go to My Case
          </Button>
        </div>
      </div>
    </Card>
  );
}
