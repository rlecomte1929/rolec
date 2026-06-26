import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { logger } from '../lib/logger';
import { EmployeeScopedAssignmentPicker } from '../components/employee/EmployeeScopedAssignmentPicker';
import { Alert, Button, Card } from '../components/antigravity';
import { RefreshButton } from '../components/RefreshButton';
import { API_BASE_URL, employeeAPI } from '../api/client';
import { buildRoute } from '../navigation/routes';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import {
  parseAssignmentSearchParam,
  setPreferredEmployeeAssignmentId,
} from '../utils/employeeAssignmentScope';
import { useServicesScope } from '../features/services/useServicesScope';
import { TrustBlock } from '../features/services/TrustBlock';
import { ServiceGroupSection } from '../features/services/ServiceGroupSection';
import { StickyContinueBar } from '../features/services/StickyContinueBar';
import { ServicesNavRibbon } from '../features/services/ServicesNavRibbon';
import { SERVICE_CONFIG, type ServiceItem, type ServiceKey } from '../features/services/serviceConfig';
import { useServicesFlow } from '../features/services/ServicesFlowContext';
import {
  SERVICES_DISPLAY_CURRENCIES,
  SERVICES_DISPLAY_CURRENCY_STORAGE_KEY,
} from '../features/services/servicesCurrency';
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
    linkedSummaries,
    isLoading: assignmentLoading,
    refetch,
  } = useEmployeeAssignment();
  const queryAssignmentId = useMemo(() => parseAssignmentSearchParam(location.search), [location.search]);
  const { assignmentId, needsPicker, linkTo } = useServicesScope();

  useEffect(() => {
    if (!queryAssignmentId || needsPicker || assignmentId !== queryAssignmentId) return;
    setPreferredEmployeeAssignmentId(queryAssignmentId);
  }, [queryAssignmentId, needsPicker, assignmentId]);
  const queryClient = useQueryClient();
  // `services` is form-local (toggled by handleToggle), seeded from the query.
  const [services, setServices] = useState<Record<string, ServiceState>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState('');
  const { setSelectedServices, displayCurrency, setDisplayCurrency, setActiveCaseId } = useServicesFlow();
  const navigate = useNavigate();

  const servicesQuery = useQuery({
    queryKey: ['employee', 'assignment-services', assignmentId],
    queryFn: async () => {
      const [serviceRes, ctxRes] = await Promise.all([
        employeeAPI.getAssignmentServices(assignmentId!),
        employeeAPI.getServicesPolicyContext(assignmentId!).catch(() => null),
      ]);
      return { serviceRes, ctxRes };
    },
    enabled: !assignmentLoading && !!assignmentId && !needsPicker,
  });

  const svcPolicy: Awaited<ReturnType<typeof employeeAPI.getServicesPolicyContext>> | null =
    servicesQuery.data?.ctxRes ?? null;
  const isLoading = servicesQuery.isLoading;
  const load401 =
    (servicesQuery.error as { response?: { status?: number } } | null)?.response?.status === 401;
  const loadError = servicesQuery.isError && !load401 ? 'Couldn’t load services data. Try again.' : '';
  const loadErrorDetails = useMemo(() => {
    if (!servicesQuery.isError || load401) return '';
    const err = servicesQuery.error as {
      response?: { status?: number; data?: { detail?: string; message?: string } };
      config?: { url?: string };
      message?: string;
    } | null;
    if (import.meta.env.DEV) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message;
      return `status=${status || 'n/a'} url=${err?.config?.url || ''} detail=${detail || ''}`;
    }
    if (!API_BASE_URL) return 'Missing VITE_API_URL in frontend build.';
    return '';
  }, [servicesQuery.isError, servicesQuery.error, load401]);

  useEffect(() => {
    setActiveCaseId(assignmentId || null);
    return () => setActiveCaseId(null);
  }, [assignmentId, setActiveCaseId]);
  const [pendingCurrency, setPendingCurrency] = useState<string>(displayCurrency);
  // Keep the picker in sync if the committed currency changes from elsewhere
  // (e.g. when policy resolution forces a default on first load).
  useEffect(() => {
    setPendingCurrency(displayCurrency);
  }, [displayCurrency]);

  useEffect(() => {
    if (!svcPolicy?.currency) return;
    try {
      if (localStorage.getItem(SERVICES_DISPLAY_CURRENCY_STORAGE_KEY)) return;
      setDisplayCurrency(String(svcPolicy.currency));
    } catch {
      // ignore
    }
  }, [svcPolicy?.currency, setDisplayCurrency]);

  // Seed the form-local `services` map from the loaded data, and sync the
  // selected set to context so the questions page has the right selection on a
  // direct visit.
  useEffect(() => {
    const serviceRes = servicesQuery.data?.serviceRes;
    if (!serviceRes) return;
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
    const selected = new Set(
      (serviceRes.services || [])
        .filter((r) => r.selected)
        .map((r) => r.service_key as ServiceKey)
    );
    setSelectedServices(selected);
  }, [servicesQuery.data?.serviceRes, setSelectedServices]);

  // Preserve the 401 → landing redirect from the read.
  useEffect(() => {
    if (servicesQuery.isError && load401) {
      navigate(buildRoute('landing'));
    }
  }, [servicesQuery.isError, load401, navigate]);

  // DEV-only diagnostics for a non-401 load failure (matches the old catch).
  useEffect(() => {
    if (servicesQuery.isError && !load401 && import.meta.env.DEV) {
      logger.error('[services] load error', servicesQuery.error);
    }
  }, [servicesQuery.isError, servicesQuery.error, load401]);

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
          currency: displayCurrency,
        };
      });
      await employeeAPI.saveAssignmentServices(assignmentId, payload);
      setMessage('Saved.');
      // Refetch so the form re-seeds from the saved server state.
      await queryClient.invalidateQueries({ queryKey: ['employee', 'assignment-services', assignmentId] });
      return true;
    } catch (err: unknown) {
      const errAny = err as { response?: { data?: { detail?: string; message?: string } }; message?: string };
      const detail = errAny?.response?.data?.detail || errAny?.response?.data?.message || errAny?.message;
      const friendly = detail === 'Network Error' ? 'Couldn’t save. Try again.' : detail;
      setMessage(friendly || "Couldn't save. Try again.");
      if (import.meta.env.DEV && detail) {
        logger.error('[services] save error', err);
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
    navigate(linkTo('questions'));
  };

  if (assignmentLoading || isLoading) {
    return (
      <AppShell section="Employee" title="Services">
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
      <AppShell section="Employee" title="Services" subtitle="Choose which move to work on.">
        <EmployeeScopedAssignmentPicker
          title="Which move are you working on?"
          subtitle="Choose the move you want to work on. You can switch anytime from your dashboard."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('services')}
        />
      </AppShell>
    );
  }

  if (!assignmentId) {
    return (
      <AppShell section="Employee" title="Services" subtitle="Select what you need for this move.">
        <Alert variant="info" className="mb-6">
          <p className="mb-3">No case linked. Select a case to access services for this relocation.</p>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => navigate(buildRoute('employeeJourney'))}>
              Start relocation setup
            </Button>
            <RefreshButton onClick={() => refetch()} label="Refresh assignment" />
            <Button variant="outline" onClick={() => navigate(buildRoute('employeeDashboard'))}>
              Back to Dashboard
            </Button>
          </div>
        </Alert>
      </AppShell>
    );
  }

  return (
    <AppShell section="Employee" title="Services">
      <div className="mb-6">
        <p className="text-[#6b7280]">Select what you need. We save it for the next steps.</p>
        <p className="text-sm text-[#94a3b8] mt-1">~3 min to complete</p>
        <div className="mt-4 rounded-lg border border-[#e2e8f0] bg-[#fafbfc] px-4 py-3">
          <label className="block">
            <span className="text-sm font-medium text-[#0b2b43]">Estimate currency</span>
            <p className="text-xs text-[#64748b] mt-0.5 mb-2">
              Set it once — Preferences, Recommendations and Review &amp; budget all use it
              (converted from USD using indicative rates).
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#0b2b43] w-full max-w-xs"
                value={pendingCurrency}
                onChange={(e) => setPendingCurrency(e.target.value)}
                aria-label="Currency for service estimates"
              >
                {SERVICES_DISPLAY_CURRENCIES.map((o) => (
                  <option key={o.code} value={o.code}>
                    {o.label}
                  </option>
                ))}
              </select>
              <Button
                onClick={() => setDisplayCurrency(pendingCurrency)}
                disabled={pendingCurrency === displayCurrency}
                aria-label={
                  pendingCurrency === displayCurrency
                    ? 'No change to apply — currency already set'
                    : `Apply ${pendingCurrency} as the estimate currency`
                }
              >
                Apply
              </Button>
              {pendingCurrency !== displayCurrency && (
                <span className="text-xs text-[#94a3b8]">
                  Currently using {displayCurrency} — click Apply to switch.
                </span>
              )}
            </div>
          </label>
        </div>
        {svcPolicy?.comparison_available && (
          <div className="mt-4 p-3 rounded-lg border border-[#bbf7d0] bg-[#f0fdf4]">
            <p className="text-sm font-medium text-[#166534]">Company policy comparison is active</p>
            <p className="text-xs text-[#15803d] mt-1">
              Supported categories show limits from your published assignment policy (resolved benefits). Partial or
              out-of-scope categories are labeled on each card.
            </p>
          </div>
        )}
      </div>
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
            </div>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-8">
              <TrustBlock className="mb-0 flex-1 min-w-0" />
              <div className="shrink-0 self-end sm:self-auto">
                <Button variant="outline" onClick={handleSave} disabled={isLoading || isSaving}>
                  {isSaving ? 'Saving...' : 'Save'}
                </Button>
              </div>
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
