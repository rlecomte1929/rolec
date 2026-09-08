import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useSearchParams, useNavigate, useParams, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../components/employee/EmployeeScopedAssignmentPicker';
import { buildRoute } from '../navigation/routes';
import { Card, Button } from '../components/antigravity';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { resourcesAPI } from '../api/client';
import { parseAssignmentSearchParam, resolveScopedAssignmentId } from '../utils/employeeAssignmentScope';
import { getAuthItem } from '../utils/demo';
import {
  ResourcesPageContent,
  EMPTY_RESOURCES_FILTERS,
  type ResourcesFilters,
} from '../features/resources/ResourcesPageContent';
import type { ResourcesPagePayload } from '../types';

function useResourcesContext() {
  const { caseId: caseIdParam } = useParams<{ caseId: string }>();
  const location = useLocation();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
    isLoading: assignmentLoading,
  } = useEmployeeAssignment();

  const queryAssignmentId = useMemo(
    () => parseAssignmentSearchParam(location.search),
    [location.search]
  );

  const scoped = useMemo(() => {
    if (caseIdParam) {
      return {
        effectiveId: caseIdParam,
        needsPicker: false,
        source: 'case' as const,
      };
    }
    const { effectiveId, needsPicker } = resolveScopedAssignmentId({
      linkedSummaries,
      primaryAssignmentId,
      queryAssignmentId,
    });
    return {
      effectiveId,
      needsPicker,
      source: 'assignment' as const,
    };
  }, [caseIdParam, linkedSummaries, primaryAssignmentId, queryAssignmentId]);

  return {
    effectiveId: scoped.effectiveId,
    source: scoped.source,
    needsPicker: scoped.needsPicker,
    linkedSummaries,
    isLoading: !caseIdParam && assignmentLoading,
    isCaseRoute: !!caseIdParam,
  };
}

export const Resources: React.FC = () => {
  const navigate = useNavigate();
  const {
    effectiveId,
    needsPicker,
    linkedSummaries,
    isLoading: contextLoading,
    isCaseRoute,
  } = useResourcesContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const [payload, setPayload] = useState<ResourcesPagePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filters: ResourcesFilters = useMemo(() => {
    const f: ResourcesFilters = { ...EMPTY_RESOURCES_FILTERS };
    searchParams.forEach((v, k) => {
      if (k in f) (f as Record<string, string>)[k] = v;
    });
    return f;
  }, [searchParams]);

  const updateFilters = useCallback(
    (next: Partial<ResourcesFilters>) => {
      const merged = { ...filters, ...next };
      const params = new URLSearchParams(searchParams);
      Object.entries(merged).forEach(([k, v]) => {
        if (v) params.set(k, v);
        else params.delete(k);
      });
      setSearchParams(params, { replace: true });
    },
    [filters, searchParams, setSearchParams]
  );

  const clearFilters = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  useEffect(() => {
    if (!effectiveId || contextLoading) {
      setLoading(false);
      setPayload(null);
      return;
    }
    setLoading(true);
    setError(null);
    const raw = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
    const filterObj: Record<string, string | boolean> = {};
    if (raw.city) filterObj.city = raw.city;
    if (raw.family) filterObj.audienceType = raw.family;
    if (raw.childAge) filterObj.childAge = raw.childAge;
    if (raw.budget) filterObj.budgetTier = raw.budget;
    if (raw.category) filterObj.category = raw.category;
    if (raw.language) filterObj.language = raw.language;
    if (raw.free) filterObj.isFree = raw.free === 'true';
    if (raw.familyFriendly) filterObj.familyFriendly = raw.familyFriendly === 'true';
    if (raw.weekendOnly) filterObj.weekendOnly = raw.weekendOnly === 'true';
    if (raw.eventType) filterObj.eventType = raw.eventType;
    if (raw.search) filterObj.search = raw.search;
    resourcesAPI
      .getPage(effectiveId, Object.keys(filterObj).length ? filterObj : undefined)
      .then(setPayload)
      .catch((err: unknown) => {
        const msg =
          (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ||
          (err as Error)?.message ||
          'Unable to load resources';
        setError(String(msg));
        setPayload(null);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveId, contextLoading, JSON.stringify(filters)]);

  const hasDestination = Boolean(payload?.context?.countryCode);

  // Role-aware breadcrumb section so employees see 'Employee' (not 'HR Operations').
  // Mirrors AIQ-548 (InboxV2Page). ADMIN keeps 'HR Operations'.
  const role = (getAuthItem('relopass_role') || '').toUpperCase();
  const sectionLabel = role === 'EMPLOYEE' ? 'Employee' : 'HR Operations';

  if (contextLoading || (loading && !payload && !(needsPicker && !isCaseRoute))) {
    return (
      <AppShell section={sectionLabel} title="Resources" subtitle="Destination guides, events and local resources for your relocation.">
        <div className="flex flex-col items-center justify-center py-16 text-[#6b7280]">
          <div className="animate-pulse h-8 w-48 bg-[#e2e8f0] rounded mb-4" />
          <div className="animate-pulse h-4 w-64 bg-[#e2e8f0] rounded" />
        </div>
      </AppShell>
    );
  }

  if (!isCaseRoute && needsPicker && linkedSummaries.length > 0) {
    return (
      <AppShell section={sectionLabel} title="Resources" subtitle="Destination guides, events and local resources for your relocation.">
        <EmployeeScopedAssignmentPicker
          title="Which assignment?"
          subtitle="Resources load per assignment."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('resources')}
        />
      </AppShell>
    );
  }

  if (!effectiveId) {
    return (
      <AppShell section={sectionLabel} title="Resources" subtitle="Destination guides, events and local resources for your relocation.">
        <Card padding="lg">
          <p className="text-[#4b5563]">
            Open a case and set a destination to see local resources here.
            {!isCaseRoute && ' Or open Resources from a case.'}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={() => navigate(buildRoute('employeeJourney'))}>
              Start relocation setup
            </Button>
            <Button variant="outline" onClick={() => navigate(buildRoute('employeeDashboard'))}>
              Go to dashboard
            </Button>
          </div>
        </Card>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell section={sectionLabel} title="Resources" subtitle="Destination guides, events and local resources for your relocation.">
        <Card padding="lg" className="border-red-200 bg-red-50">
          <p className="text-red-700">{error}</p>
          <Button variant="secondary" className="mt-4" onClick={() => window.location.reload()}>
            Retry
          </Button>
        </Card>
      </AppShell>
    );
  }

  if (!hasDestination || !payload) {
    return (
      <AppShell section={sectionLabel} title="Resources" subtitle="Destination guides, events and local resources for your relocation.">
        <Card padding="lg">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-2">Set a destination first</h2>
          <p className="text-[#4b5563] mb-4">
            Finish intake with country and city. Then this page shows local resources for that destination.
          </p>
          <Button onClick={() => navigate(buildRoute('employeeDashboard'))}>Go to dashboard</Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell section={sectionLabel} title="Resources" subtitle="Guides and events for your destination.">
      <ResourcesPageContent
        payload={payload}
        filters={filters}
        updateFilters={updateFilters}
        clearFilters={clearFilters}
      />
    </AppShell>
  );
};
