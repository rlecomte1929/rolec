import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Badge, Button, Card, Input } from '../components/antigravity';
import { employeeAPI } from '../api/client';
import { buildRoute } from '../navigation/routes';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { TrustBlock } from '../features/services/TrustBlock';
import { ServiceGroupSection } from '../features/services/ServiceGroupSection';
import { StickyContinueBar } from '../features/services/StickyContinueBar';
import { SERVICE_CONFIG, type ServiceKey } from '../features/services/serviceConfig';

const ENABLED_SERVICES = SERVICE_CONFIG.filter((svc) => svc.enabled);

const CATEGORY_MAP: Record<ServiceKey, string> = {
  visa: 'immigration',
  housing: 'housing',
  schools: 'schools',
  childcare: 'schools',
  movers: 'moving',
  temp_accommodation: 'housing',
  banks: 'settling_in',
  insurances: 'settling_in',
  registration: 'settling_in',
  electricity: 'settling_in',
  internet: 'settling_in',
  mobile: 'settling_in',
  transport: 'settling_in',
  drivers_license: 'settling_in',
  language: 'settling_in',
  spouse: 'settling_in',
  community: 'settling_in',
};

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
        ENABLED_SERVICES.forEach((svc) => {
          baseState[svc.key] = { selected: false, estimated_cost: '' };
        });
        serviceRes.services?.forEach((row) => {
          if (!baseState[row.service_key]) return;
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
    ENABLED_SERVICES.forEach((svc) => {
      const state = services[svc.key] || { selected: false, estimated_cost: '' };
      if (!state?.selected) return;
      const cost = Number(state.estimated_cost);
      if (!Number.isFinite(cost)) return;
      const category = CATEGORY_MAP[svc.key] || 'other';
      byCategory[category] = (byCategory[category] || 0) + cost;
      total += cost;
    });
    return { byCategory, total };
  }, [services]);

  const selectedKeys = useMemo(
    () => new Set(Object.entries(services).filter(([, v]) => v.selected).map(([k]) => k)),
    [services]
  );

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
      const payload = ENABLED_SERVICES.map((svc) => {
        const state = services[svc.key] || { selected: false, estimated_cost: '' };
        return {
          service_key: svc.key,
          category: CATEGORY_MAP[svc.key] || 'other',
          selected: state.selected,
          estimated_cost: state.estimated_cost ? Number(state.estimated_cost) : null,
          currency: policy?.currency || 'EUR',
        };
      });
      await employeeAPI.saveAssignmentServices(assignmentId, payload);
      setMessage('Saved services successfully.');
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message;
      setMessage(detail || 'Unable to save services. Please try again.');
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
        <div className="lg:col-span-2 space-y-6">
          <Card padding="lg">
            <div className="mb-6">
              <h1 className="text-2xl font-semibold text-[#0b2b43] mb-2">Your relocation plan</h1>
              <p className="text-[#6b7280]">
                Select the areas where you need support — we’ll build a clear plan so nothing falls through the cracks.
              </p>
            </div>
            <TrustBlock className="mb-8" />
            <ServiceGroupSection
              group="before"
              items={ENABLED_SERVICES.filter((s) => s.group === 'before')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
            />
            <ServiceGroupSection
              group="arrival"
              items={ENABLED_SERVICES.filter((s) => s.group === 'arrival')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
            />
            <ServiceGroupSection
              group="settle"
              items={ENABLED_SERVICES.filter((s) => s.group === 'settle')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
            />
            <StickyContinueBar
              selectedCount={selectedKeys.size}
              onContinue={handleSave}
              buttonLabel="Save services"
            />
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
            <div className="text-lg font-semibold text-[#0b2b43] mb-2">Estimated costs</div>
            <div className="space-y-3 text-sm">
              {ENABLED_SERVICES.filter((svc) => services[svc.key]?.selected).length === 0 && (
                <div className="text-[#6b7280]">Select services to add estimates.</div>
              )}
              {ENABLED_SERVICES.filter((svc) => services[svc.key]?.selected).map((svc) => {
                const state = services[svc.key] || { selected: false, estimated_cost: '' };
                const category = CATEGORY_MAP[svc.key] || 'other';
                const cap = policy?.caps?.[category];
                return (
                  <div key={svc.key} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="font-medium text-[#0b2b43]">{svc.title}</div>
                      <Badge variant="neutral">{category.replace('_', ' ')}</Badge>
                    </div>
                    <Input
                      type="number"
                      label="Estimated cost"
                      value={state.estimated_cost}
                      onChange={(value) => handleCostChange(svc.key, value)}
                      placeholder="0"
                      fullWidth
                    />
                    <div className="text-xs text-[#6b7280]">
                      Policy cap: {cap ? `${policy?.currency} ${cap}` : 'policy not provided'}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
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
