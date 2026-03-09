import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card } from '../components/antigravity';
import { API_BASE_URL, employeeAPI } from '../api/client';
import { buildRoute } from '../navigation/routes';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { TrustBlock } from '../features/services/TrustBlock';
import { ServiceGroupSection } from '../features/services/ServiceGroupSection';
import { StickyContinueBar } from '../features/services/StickyContinueBar';
import { ServicesNavRibbon } from '../features/services/ServicesNavRibbon';
import { SERVICE_CONFIG, type ServiceKey } from '../features/services/serviceConfig';
import { useServicesFlow } from '../features/services/ServicesFlowContext';

const ENABLED_SERVICES = SERVICE_CONFIG.filter((svc) => svc.enabled);
const ALL_SERVICES = SERVICE_CONFIG;

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
  const { assignmentId, isLoading: assignmentLoading, refetch } = useEmployeeAssignment();
  const [services, setServices] = useState<Record<string, ServiceState>>({});
  const [policy, setPolicy] = useState<{ currency: string; caps: Record<string, number>; total_cap?: number | null } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [loadError, setLoadError] = useState('');
  const [loadErrorDetails, setLoadErrorDetails] = useState('');
  const { setSelectedServices } = useServicesFlow();
  const navigate = useNavigate();

  useEffect(() => {
    if (assignmentLoading) return;
    if (!assignmentId) {
      setIsLoading(false);
      return;
    }
    const load = async () => {
      setIsLoading(true);
      setLoadError('');
      setLoadErrorDetails('');
      try {
        const serviceRes = await employeeAPI.getAssignmentServices(assignmentId);
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
        try {
          const policyRes = await employeeAPI.getPolicyBudget(assignmentId);
          setPolicy(policyRes);
        } catch {
          // policy budget is optional; keep services usable
          setPolicy(null);
        }
      } catch (err: any) {
        if (err?.response?.status === 401) {
          navigate(buildRoute('landing'));
          return;
        }
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message;
        setLoadError('Couldn’t load services data. Please retry.');
        if (import.meta.env.DEV) {
          setLoadErrorDetails(`status=${status || 'n/a'} url=${err?.config?.url || ''} detail=${detail || ''}`);
          // eslint-disable-next-line no-console
          console.error('[services] load error', err);
        }
        if (!API_BASE_URL && !import.meta.env.DEV) {
          setLoadErrorDetails('Missing VITE_API_URL in frontend build.');
        }
        setPolicy(null);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [assignmentId, assignmentLoading, navigate]);

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

  const handleSave = async () => {
    if (!assignmentId) return;
    // keep minimal UI state changes
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
      return true;
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message;
      const friendly = detail === 'Network Error' ? 'Couldn’t save services. Please retry.' : detail;
      setMessage(friendly || 'Unable to save services. Please try again.');
      if (import.meta.env.DEV && detail) {
        // eslint-disable-next-line no-console
        console.error('[services] save error', err);
      }
      return false;
    } finally {
      // no-op
    }
  };

  const handleContinue = async () => {
    const ok = await handleSave();
    if (!ok) return;
    const selected = new Set(
      Object.entries(services)
        .filter(([, v]) => v.selected)
        .map(([k]) => k as ServiceKey)
    );
    setSelectedServices(selected);
    navigate(buildRoute('servicesQuestions'));
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
          <p className="mb-3">No assignment found. You need an active assignment to use Services. If you completed the intake wizard, try refreshing your assignment.</p>
          <div className="flex gap-3">
            <Button onClick={() => refetch()}>Refresh assignment</Button>
            <Button variant="outline" onClick={() => navigate(buildRoute('employeeDashboard'))}>
              Back to Dashboard
            </Button>
          </div>
        </Alert>
      </AppShell>
    );
  }

  return (
    <AppShell title="Services" subtitle="Choose the services you need for your relocation.">
      <ServicesNavRibbon />
      {loadError && (
        <Alert variant="error" className="mb-6">
          <div className="space-y-2">
            <div>{loadError}</div>
            {loadErrorDetails && (
              <div className="text-xs text-[#6b7280]">{loadErrorDetails}</div>
            )}
            <div>
              <Button variant="outline" onClick={() => window.location.reload()}>
                Retry
              </Button>
            </div>
          </div>
        </Alert>
      )}
      {message && (
        <Alert variant={message.includes('Saved') ? 'success' : 'error'} className="mb-6">
          {message}
        </Alert>
      )}

      <div className="w-full">
        <Card padding="lg">
            <div className="mb-6">
              <h1 className="text-2xl font-semibold text-[#0b2b43] mb-2">Your relocation plan</h1>
              <p className="text-[#6b7280]">
                Select the areas where you need support — we’ll build a clear plan so nothing falls through the cracks.
              </p>
              <p className="text-sm text-[#94a3b8] mt-1">~3 min to complete</p>
            </div>
            <TrustBlock className="mb-8" />
            <ServiceGroupSection
              group="before"
              items={ALL_SERVICES.filter((s) => s.group === 'before')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
            />
            <ServiceGroupSection
              group="arrival"
              items={ALL_SERVICES.filter((s) => s.group === 'arrival')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
            />
            <ServiceGroupSection
              group="settle"
              items={ALL_SERVICES.filter((s) => s.group === 'settle')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
            />
            <StickyContinueBar
              selectedCount={selectedKeys.size}
              onContinue={handleContinue}
              buttonLabel="Continue to questions"
            />
          </Card>
      </div>
    </AppShell>
  );
};
