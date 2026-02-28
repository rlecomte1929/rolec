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
