import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../components/employee/EmployeeScopedAssignmentPicker';
import { Alert, Button, Card } from '../components/antigravity';
import { API_BASE_URL, employeeAPI } from '../api/client';
import { buildRoute } from '../navigation/routes';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import {
  parseAssignmentSearchParam,
  resolveScopedAssignmentId,
  setPreferredEmployeeAssignmentId,
  withAssignmentQuery,
} from '../utils/employeeAssignmentScope';
import { TrustBlock } from '../features/services/TrustBlock';
import { ServiceGroupSection } from '../features/services/ServiceGroupSection';
import { StickyContinueBar } from '../features/services/StickyContinueBar';
import { ServicesNavRibbon } from '../features/services/ServicesNavRibbon';
import { SERVICE_CONFIG, type ServiceItem, type ServiceKey } from '../features/services/serviceConfig';
import { useServicesFlow } from '../features/services/ServicesFlowContext';
import type { ServicePolicyHint } from '../features/services/ServiceCard';
import {
  EMPLOYEE_HR_POLICY_WAIT_PRIMARY,
  EMPLOYEE_HR_POLICY_WAIT_SECONDARY,
  EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_PRIMARY,
  EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_SECONDARY,
} from '../features/policy/employeePolicyMessages';

type ServicesCategoryEntry = NonNullable<
  Awaited<ReturnType<typeof employeeAPI.getServicesPolicyContext>>['categories']
>[string];

function policyHintFromCategory(entry: ServicesCategoryEntry | undefined): ServicePolicyHint | undefined {
  if (!entry) return undefined;
  const { determination, show_policy_comparison, primary_label } = entry;
  let variant: ServicePolicyHint['variant'] = 'muted';
  if (show_policy_comparison) variant = 'compare';
  else if (determination === 'excluded') variant = 'excluded';
  else if (
    determination === 'out_of_scope' ||
    determination === 'no_published_policy' ||
    determination === 'no_benefit_rule'
  )
    variant = 'muted';
  else variant = 'partial';
  return { variant, line: primary_label };
}

const ENABLED_SERVICES = SERVICE_CONFIG.filter((svc) => svc.enabled);
const ALL_SERVICES = SERVICE_CONFIG;

const CATEGORY_MAP: Record<ServiceKey, string> = {
  visa: 'immigration',
  housing: 'housing',
  schools: 'schools',
  childcare: 'schools',
  movers: 'moving',
  pets: 'moving',
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
  const location = useLocation();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
    isLoading: assignmentLoading,
    refetch,
  } = useEmployeeAssignment();
  const queryAssignmentId = useMemo(() => parseAssignmentSearchParam(location.search), [location.search]);
  const { effectiveId: assignmentId, needsPicker } = useMemo(
    () =>
      resolveScopedAssignmentId({
        linkedSummaries,
        primaryAssignmentId,
        queryAssignmentId,
      }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId]
  );

  useEffect(() => {
    if (!queryAssignmentId || needsPicker || assignmentId !== queryAssignmentId) return;
    setPreferredEmployeeAssignmentId(queryAssignmentId);
  }, [queryAssignmentId, needsPicker, assignmentId]);
  const [services, setServices] = useState<Record<string, ServiceState>>({});
  const [svcPolicy, setSvcPolicy] = useState<Awaited<ReturnType<typeof employeeAPI.getServicesPolicyContext>> | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [loadError, setLoadError] = useState('');
  const [loadErrorDetails, setLoadErrorDetails] = useState('');
  const { setSelectedServices } = useServicesFlow();
  const navigate = useNavigate();

  useEffect(() => {
    if (assignmentLoading) return;
    if (!assignmentId || needsPicker) {
      setIsLoading(false);
      return;
    }
    const load = async () => {
      setIsLoading(true);
      setLoadError('');
      setLoadErrorDetails('');
      try {
        const [serviceRes, ctxRes] = await Promise.all([
          employeeAPI.getAssignmentServices(assignmentId),
          employeeAPI.getServicesPolicyContext(assignmentId).catch(() => null),
        ]);
        setSvcPolicy(ctxRes);
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
        // Sync selected services to context so questions page has correct selection on direct visit
        const selected = new Set(
          (serviceRes.services || [])
            .filter((r) => r.selected)
            .map((r) => r.service_key as ServiceKey)
        );
        setSelectedServices(selected);
      } catch (err: any) {
        if (err?.response?.status === 401) {
          navigate(buildRoute('landing'));
          return;
        }
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message;
        setLoadError('Couldn’t load services data. Try again.');
        if (import.meta.env.DEV) {
          setLoadErrorDetails(`status=${status || 'n/a'} url=${err?.config?.url || ''} detail=${detail || ''}`);
          // eslint-disable-next-line no-console
          console.error('[services] load error', err);
        }
        if (!API_BASE_URL && !import.meta.env.DEV) {
          setLoadErrorDetails('Missing VITE_API_URL in frontend build.');
        }
        setSvcPolicy(null);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [assignmentId, assignmentLoading, needsPicker, navigate]);

  const selectedKeys = useMemo(
    () => new Set(Object.entries(services).filter(([, v]) => v.selected).map(([k]) => k)),
    [services]
  );

  const policyHintForItem = useCallback(
    (item: ServiceItem) => {
      const bk = item.backendKey;
      if (!bk || !svcPolicy?.categories) return undefined;
      return policyHintFromCategory(svcPolicy.categories[bk]);
    },
    [svcPolicy]
  );

  const handleToggle = (key: string) => {
    setServices((prev) => ({
      ...prev,
      [key]: { selected: !prev[key]?.selected, estimated_cost: prev[key]?.estimated_cost || '' },
    }));
  };

  const handleSave = async () => {
    if (!assignmentId) return;
    setMessage('');
    setIsSaving(true);
    try {
      const payload = ENABLED_SERVICES.map((svc) => {
        const state = services[svc.key] || { selected: false, estimated_cost: '' };
        return {
          service_key: svc.key,
          category: CATEGORY_MAP[svc.key] || 'other',
          selected: state.selected,
          estimated_cost: state.estimated_cost ? Number(state.estimated_cost) : null,
          currency: svcPolicy?.currency || 'EUR',
        };
      });
      await employeeAPI.saveAssignmentServices(assignmentId, payload);
      setMessage('Saved.');
      return true;
    } catch (err: unknown) {
      const errAny = err as { response?: { data?: { detail?: string; message?: string } }; message?: string };
      const detail = errAny?.response?.data?.detail || errAny?.response?.data?.message || errAny?.message;
      const friendly = detail === 'Network Error' ? 'Couldn’t save. Try again.' : detail;
      setMessage(friendly || "Couldn't save. Try again.");
      if (import.meta.env.DEV && detail) {
        // eslint-disable-next-line no-console
        console.error('[services] save error', err);
      }
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleContinue = async () => {
    const ok = await handleSave();
    if (!ok) return;
    if (!assignmentId) return;
    const selected = new Set(
      Object.entries(services)
        .filter(([, v]) => v.selected)
        .map(([k]) => k as ServiceKey)
    );
    setSelectedServices(selected);
    navigate(withAssignmentQuery(buildRoute('servicesQuestions'), assignmentId));
  };

  if (assignmentLoading || isLoading) {
    return (
      <AppShell title="Services" subtitle="Select what you need for this move.">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0b2b43] mx-auto mb-4" />
          <p className="text-[#0b2b43] font-medium">Loading services and policy context…</p>
          <p className="text-sm text-[#6b7280] mt-2">
            We load your selections together with published policy hints when available. If policy data is missing, the page will still open with clear messaging.
          </p>
        </div>
      </AppShell>
    );
  }

  if (!assignmentLoading && needsPicker && linkedSummaries.length > 0) {
    return (
      <AppShell title="Services" subtitle="Pick the assignment for this session.">
        <EmployeeScopedAssignmentPicker
          title="Which assignment are you working on?"
          subtitle="Pick one assignment for this session. Change it anytime from the dashboard or by reopening Services with another choice."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('services')}
        />
      </AppShell>
    );
  }

  if (!assignmentId) {
    return (
      <AppShell title="Services" subtitle="Select what you need for this move.">
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
    <AppShell title="Services" subtitle="Select what you need for this move.">
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
              <p className="text-[#6b7280]">Select what you need. We save it for the next steps.</p>
              <p className="text-sm text-[#94a3b8] mt-1">~3 min to complete</p>
              {svcPolicy?.comparison_available && (
                <div className="mt-4 p-3 rounded-lg border border-[#bbf7d0] bg-[#f0fdf4]">
                  <p className="text-sm font-medium text-[#166534]">Company policy comparison is active</p>
                  <p className="text-xs text-[#15803d] mt-1">
                    Supported categories show limits from your published assignment policy (resolved benefits). Partial
                    or out-of-scope categories are labeled on each card.
                  </p>
                </div>
              )}
              {svcPolicy && svcPolicy.has_policy === false && (
                <div className="mt-4 p-3 bg-[#fafbfc] border border-[#e2e8f0] rounded-lg">
                  <p className="text-sm text-[#4b5563] font-medium">{EMPLOYEE_HR_POLICY_WAIT_PRIMARY}</p>
                  <p className="text-sm text-[#6b7280] mt-2">{EMPLOYEE_HR_POLICY_WAIT_SECONDARY}</p>
                </div>
              )}
              {svcPolicy && svcPolicy.has_policy === true && svcPolicy.comparison_available === false && (
                <div className="mt-4 p-3 bg-[#fafbfc] border border-[#e2e8f0] rounded-lg">
                  <p className="text-sm text-[#4b5563] font-medium">{EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_PRIMARY}</p>
                  <p className="text-sm text-[#6b7280] mt-2">{EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_SECONDARY}</p>
                </div>
              )}
              <div className="mt-4 p-3 bg-[#eef4f8] border border-[#0b2b43]/20 rounded-lg">
                <p className="text-sm text-[#4b5563] mb-2">
                  Full policy wording and benefit details are on the HR Policy page. For questions, contact your company
                  HR.
                </p>
                <Link to={buildRoute('hrPolicy')}>
                  <Button variant="outline" className="mt-1">
                    View HR Policy &amp; limits
                  </Button>
                </Link>
              </div>
            </div>
            <TrustBlock className="mb-8" />
            <div className="flex flex-wrap items-center gap-3 mb-6">
              <Button variant="outline" onClick={handleSave} disabled={isLoading || isSaving}>
                {isSaving ? 'Saving...' : 'Save'}
              </Button>
            </div>
            <ServiceGroupSection
              group="before"
              items={ALL_SERVICES.filter((s) => s.group === 'before')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
              policyHintForItem={svcPolicy?.categories ? policyHintForItem : undefined}
            />
            <ServiceGroupSection
              group="arrival"
              items={ALL_SERVICES.filter((s) => s.group === 'arrival')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
              policyHintForItem={svcPolicy?.categories ? policyHintForItem : undefined}
            />
            <ServiceGroupSection
              group="settle"
              items={ALL_SERVICES.filter((s) => s.group === 'settle')}
              selectedKeys={selectedKeys}
              onToggle={handleToggle}
              policyHintForItem={svcPolicy?.categories ? policyHintForItem : undefined}
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
