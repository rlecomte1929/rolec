import React, {
  useEffect,
  useState,
  useMemo,
  useCallback,
  useRef,
} from 'react';
import { useSearchParams, useNavigate, useParams, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../components/employee/EmployeeScopedAssignmentPicker';
import { buildRoute } from '../navigation/routes';
import { Card, Button, Input } from '../components/antigravity';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { resourcesAPI } from '../api/client';
import { parseAssignmentSearchParam, resolveScopedAssignmentId } from '../utils/employeeAssignmentScope';
import type {
  ResourcesPagePayload,
  ResourceContext,
  PublicResource,
  PublicEvent,
  RecommendationGroup,
} from '../types';

// --- Section config (alphabetically by label) ---
const SECTIONS = [
  { id: 'admin_essentials', label: 'Admin essentials', icon: '📋', categoryKeys: ['admin_essentials', 'admin', 'registration'] },
  { id: 'community', label: 'Community', icon: '🤝', categoryKeys: ['community', 'social', 'expat'] },
  { id: 'cost_of_living', label: 'Cost of living', icon: '💰', categoryKeys: ['cost_of_living', 'cost'] },
  { id: 'daily_life', label: 'Daily life', icon: '🛒', categoryKeys: ['daily_life', 'groceries', 'shopping'] },
  { id: 'events', label: 'Events', icon: '🎭', categoryKeys: ['culture_leisure', 'events', 'cinema', 'concerts'] },
  { id: 'healthcare', label: 'Healthcare', icon: '🏥', categoryKeys: ['healthcare', 'health'] },
  { id: 'housing', label: 'Housing', icon: '🏠', categoryKeys: ['housing', 'neighborhoods'] },
  { id: 'nature', label: 'Nature', icon: '🏔️', categoryKeys: ['nature', 'parks', 'outdoor'] },
  { id: 'overview', label: 'Overview', icon: '📋', categoryKeys: ['welcome', 'essentials'] },
  { id: 'safety', label: 'Safety', icon: '🛡️', categoryKeys: ['safety', 'emergency'] },
  { id: 'schools', label: 'Schools & childcare', icon: '🎓', categoryKeys: ['schools', 'childcare', 'education'] },
  { id: 'transport', label: 'Transport', icon: '🚇', categoryKeys: ['transport', 'transportation'] },
] as const;

const EVENT_TYPE_LABELS: Record<string, string> = {
  cinema: 'Cinema',
  concert: 'Concert',
  family_activity: 'Family',
  festival: 'Festival',
  museum: 'Museum',
  networking: 'Networking',
  sports: 'Sports',
  theater: 'Theater',
};

const CATEGORY_FILTER_OPTIONS = [
  { value: '', label: 'Category' },
  ...SECTIONS.filter((s) => s.id !== 'overview' && s.id !== 'events').map((s) => ({
    value: s.id,
    label: s.label,
  })),
];

function formatEventDate(iso: string): string {
  try {
    const d = new Date(iso);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dDate = d.toDateString();
    if (dDate === today.toDateString())
      return `Today ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    if (dDate === tomorrow.toDateString())
      return `Tomorrow ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    return d.toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// --- Hook: resolve assignment/case id for API ---
function useResourcesContext() {
  const { caseId: caseIdParam } = useParams<{ caseId: string }>();
  const location = useLocation();
  const {
    assignmentId: primaryAssignmentId,
    linkedCount,
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
      linkedCount,
      linkedSummaries,
      primaryAssignmentId,
      queryAssignmentId,
    });
    return {
      effectiveId,
      needsPicker,
      source: 'assignment' as const,
    };
  }, [caseIdParam, linkedCount, linkedSummaries, primaryAssignmentId, queryAssignmentId]);

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
  const [activeSection, setActiveSection] = useState('overview');
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  const filters = useMemo(() => {
    const f: Record<string, string> = {
      city: '',
      family: '',
      childAge: '',
      budget: '',
      category: '',
      language: '',
      free: '',
      familyFriendly: '',
      weekendOnly: '',
      eventType: '',
      search: '',
    };
    searchParams.forEach((v, k) => {
      if (f[k] !== undefined) f[k] = v;
    });
    return f;
  }, [searchParams]);

  const updateFilters = useCallback(
    (next: Partial<Record<string, string>>) => {
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
    const raw = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v)
    );
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
          (err as { response?: { data?: { detail?: string } }; message?: string })
            ?.response?.data?.detail ||
          (err as Error)?.message ||
          'Unable to load resources';
        setError(String(msg));
        setPayload(null);
      })
      .finally(() => setLoading(false));
  }, [effectiveId, contextLoading, JSON.stringify(filters)]);

  const context = payload?.context ?? null;
  const destination = context
    ? [context.cityName, context.countryName].filter(Boolean).join(', ') || context.countryName || 'Your destination'
    : null;
  const hasDestination = Boolean(context?.countryCode);

  const categoryKeyById = useMemo(() => {
    const m: Record<string, string> = {};
    (payload?.categories ?? []).forEach((c) => {
      m[c.id] = c.key;
    });
    return m;
  }, [payload?.categories]);

  const resourcesBySection = useMemo(() => {
    const bySection: Record<string, PublicResource[]> = {};
    const resources = payload?.resources ?? [];
    resources.forEach((r) => {
      const catKey = r.categoryId ? categoryKeyById[r.categoryId] : null;
      const sectionId =
        SECTIONS.find((s) => s.categoryKeys.some((k) => catKey?.includes(k) || k === catKey))?.id ??
        'overview';
      if (!bySection[sectionId]) bySection[sectionId] = [];
      bySection[sectionId].push(r);
    });
    return bySection;
  }, [payload?.resources, categoryKeyById]);

  const filteredEvents = useMemo(() => {
    let list = payload?.events ?? [];
    if (filters.eventType) {
      list = list.filter(
        (e) => (e.eventType || '').toLowerCase() === filters.eventType.toLowerCase()
      );
    }
    if (filters.familyFriendly === 'true') {
      list = list.filter((e) => e.isFamilyFriendly);
    }
    if (filters.free === 'true') {
      list = list.filter((e) => e.isFree);
    }
    if (filters.weekendOnly === 'true') {
      list = list.filter((e) => {
        try {
          const d = new Date(e.startDatetime);
          return d.getDay() === 0 || d.getDay() === 6;
        } catch {
          return false;
        }
      });
    }
    return list;
  }, [payload?.events, filters.eventType, filters.familyFriendly, filters.free, filters.weekendOnly]);

  const recommended = (payload?.recommended ?? {}) as RecommendationGroup;
  const hints = payload?.hints ?? { priorities: [], recommendations: [] };

  const scrollToSection = (id: string) => {
    setActiveSection(id);
    const el = sectionRefs.current[id];
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  if (contextLoading || (loading && !payload && !(needsPicker && !isCaseRoute))) {
    return (
      <AppShell title="Resources" subtitle="Practical tips for your relocation.">
        <div className="flex flex-col items-center justify-center py-16 text-[#6b7280]">
          <div className="animate-pulse h-8 w-48 bg-[#e2e8f0] rounded mb-4" />
          <div className="animate-pulse h-4 w-64 bg-[#e2e8f0] rounded" />
        </div>
      </AppShell>
    );
  }

  if (!isCaseRoute && needsPicker && linkedSummaries.length > 0) {
    return (
      <AppShell title="Resources" subtitle="Practical tips for your relocation.">
        <EmployeeScopedAssignmentPicker
          title="Which assignment’s resources?"
          subtitle="You have multiple linked relocations. Pick one to load destination-specific guides and events."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('resources')}
        />
      </AppShell>
    );
  }

  if (!effectiveId) {
    return (
      <AppShell title="Resources" subtitle="Practical tips for your relocation.">
        <Card padding="lg">
          <p className="text-[#4b5563]">
            Complete the intake wizard and select a destination to see country-specific resources.
            {!isCaseRoute && ' Or open resources from a specific case.'}
          </p>
          <Button
            className="mt-4"
            onClick={() => navigate(buildRoute('employeeDashboard'))}
          >
            Go to dashboard
          </Button>
        </Card>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell title="Resources" subtitle="Practical tips for your relocation.">
        <Card padding="lg" className="border-red-200 bg-red-50">
          <p className="text-red-700">{error}</p>
          <Button
            variant="secondary"
            className="mt-4"
            onClick={() => window.location.reload()}
          >
            Retry
          </Button>
        </Card>
      </AppShell>
    );
  }

  if (!hasDestination) {
    return (
      <AppShell title="Resources" subtitle="Practical tips for your relocation.">
        <Card padding="lg">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-2">
            Select your destination first
          </h2>
          <p className="text-[#4b5563] mb-4">
            Complete the intake wizard and choose your destination country and city to unlock
            personalized resources, events, and practical guides for your relocation.
          </p>
          <Button onClick={() => navigate(buildRoute('employeeDashboard'))}>
            Go to dashboard
          </Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Resources"
      subtitle="Practical, structured information for your relocation."
    >
      {/* Hero */}
      <section
        ref={(el) => {
          sectionRefs.current['overview'] = el;
        }}
        className="rounded-xl bg-gradient-to-br from-[#0b2b43] to-[#1e4a6e] text-white p-6 mb-6"
      >
        <h1 className="text-2xl font-bold mb-1">
          Welcome to {destination || 'Your Destination'}
        </h1>
        <p className="text-white/90 text-sm">
          {context?.hasChildren && 'Family-focused • '}
          {context?.relocationType && `${context.relocationType.replace('_', ' ')} assignment • `}
          Based on your relocation profile, here are the most relevant resources for your move.
        </p>
        {hints.priorities?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs text-white/80">Priorities:</span>
            {hints.priorities.slice(0, 5).map((p) => (
              <span
                key={p}
                className="text-xs px-2 py-0.5 rounded-full bg-white/20"
              >
                {String(p).replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}
        {hints.recommendations?.length > 0 && (
          <div className="mt-3 p-3 rounded-lg bg-white/10">
            <div className="text-xs font-medium text-white/90 mb-1">
              Based on your profile we recommend:
            </div>
            <ul className="text-sm text-white/90 space-y-1">
              {hints.recommendations.map((r) => (
                <li key={r}>• {r}</li>
              ))}
            </ul>
          </div>
        )}
        {/* Quick callouts */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'First steps', icon: '📋', sectionId: 'admin_essentials' },
            { label: 'Housing', icon: '🏠', sectionId: 'housing' },
            { label: 'Healthcare', icon: '🏥', sectionId: 'healthcare' },
            ...(context?.hasChildren
              ? [{ label: 'Schools', icon: '🎓', sectionId: 'schools' }]
              : [{ label: 'Community', icon: '🤝', sectionId: 'community' }]),
          ].map(({ label, icon, sectionId }) => (
            <button
              key={label}
              type="button"
              onClick={() => scrollToSection(sectionId)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-left text-sm"
            >
              <span aria-hidden>{icon}</span>
              {label}
            </button>
          ))}
        </div>
      </section>

      {/* Recommendations */}
      {(recommended.recommendedForYou?.length > 0 ||
        recommended.firstSteps?.length > 0 ||
        recommended.familyEssentials?.length > 0 ||
        recommended.thisWeekend?.length > 0) && (
        <Card padding="lg" className="mb-6">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">
            Recommended for you
          </h2>
          <div className="space-y-4">
            {recommended.recommendedForYou?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-[#64748b] mb-2">
                  Top picks
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
                  {recommended.recommendedForYou.slice(0, 5).map((r) => (
                    <ResourceCard key={r.id} resource={r} />
                  ))}
                </div>
              </div>
            )}
            {recommended.firstSteps?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-[#64748b] mb-2">First steps</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {recommended.firstSteps.slice(0, 3).map((r) => (
                    <ResourceCard key={r.id} resource={r} />
                  ))}
                </div>
              </div>
            )}
            {recommended.familyEssentials?.length > 0 && context?.hasChildren && (
              <div>
                <h3 className="text-sm font-medium text-[#64748b] mb-2">
                  Family essentials
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {recommended.familyEssentials.slice(0, 3).map((r) => (
                    <ResourceCard key={r.id} resource={r} />
                  ))}
                </div>
              </div>
            )}
            {recommended.thisWeekend?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-[#64748b] mb-2">
                  This week in {context?.cityName || 'your city'}
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {recommended.thisWeekend.slice(0, 3).map((e) => (
                    <EventCard key={e.id} event={e} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Filters */}
      <Card padding="md" className="mb-6">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-40 sm:w-48">
            <Input
              placeholder="Search..."
              value={filters.search}
              onChange={(value) => updateFilters({ search: value })}
            />
          </div>
          <select
            value={filters.city}
            onChange={(e) => updateFilters({ city: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">City</option>
            {context?.cityName && (
              <option value={context.cityName}>{context.cityName}</option>
            )}
          </select>
          <select
            value={filters.family}
            onChange={(e) => updateFilters({ family: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">Family type</option>
            <option value="single">Single</option>
            <option value="couple">Couple</option>
            <option value="family">Family</option>
          </select>
          <select
            value={filters.childAge}
            onChange={(e) => updateFilters({ childAge: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">Child age</option>
            <option value="0-3">0–3</option>
            <option value="4-6">4–6</option>
            <option value="7-12">7–12</option>
            <option value="13-18">13–18</option>
          </select>
          <select
            value={filters.budget}
            onChange={(e) => updateFilters({ budget: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">Budget</option>
            <option value="low">Low</option>
            <option value="mid">Mid</option>
            <option value="high">High</option>
          </select>
          <select
            value={filters.category}
            onChange={(e) => updateFilters({ category: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            {CATEGORY_FILTER_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={filters.free}
            onChange={(e) => updateFilters({ free: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">Free / Paid</option>
            <option value="true">Free only</option>
          </select>
          <select
            value={filters.familyFriendly}
            onChange={(e) => updateFilters({ familyFriendly: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">Family-friendly</option>
            <option value="true">Yes</option>
          </select>
          <select
            value={filters.eventType}
            onChange={(e) => updateFilters({ eventType: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">Event type</option>
            {Object.entries(EVENT_TYPE_LABELS).sort(([, a], [, b]) => a.localeCompare(b)).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <select
            value={filters.weekendOnly}
            onChange={(e) => updateFilters({ weekendOnly: e.target.value })}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">Weekday / Weekend</option>
            <option value="true">Weekend only</option>
          </select>
          {(Object.values(filters).some(Boolean) && (
            <Button variant="secondary" onClick={clearFilters}>
              Clear filters
            </Button>
          )) || null}
        </div>
      </Card>

      {/* Section nav */}
      <nav
        className="flex gap-1 overflow-x-auto pb-2 mb-6 border-b border-[#e2e8f0] -mx-2 px-2"
        aria-label="Resource sections"
      >
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => scrollToSection(s.id)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium whitespace-nowrap transition-colors ${
              activeSection === s.id
                ? 'bg-[#0b2b43] text-white'
                : 'bg-[#f8fafc] text-[#4b5563] hover:bg-[#eef2f7]'
            }`}
          >
            <span className="mr-1" aria-hidden>{s.icon}</span>
            {s.label}
          </button>
        ))}
      </nav>

      {/* Content modules */}
      <div className="space-y-8">
        {SECTIONS.filter((s) => s.id !== 'events').map((section) => {
          const items = resourcesBySection[section.id] ?? [];
          if (items.length === 0 && section.id !== 'overview') return null;
          const searchQ = filters.search?.toLowerCase();
          const filtered =
            searchQ && items.length
              ? items.filter(
                  (r) =>
                    (r.title || '').toLowerCase().includes(searchQ) ||
                    (r.summary || '').toLowerCase().includes(searchQ)
                )
              : items;

          return (
            <section
              key={section.id}
              ref={(el) => {
                sectionRefs.current[section.id] = el;
              }}
              onMouseEnter={() => setActiveSection(section.id)}
            >
              <ResourceSection
                sectionId={section.id}
                label={section.label}
                icon={section.icon}
                resources={filtered}
              />
            </section>
          );
        })}

        {/* Events */}
        <section
          ref={(el) => {
            sectionRefs.current['events'] = el;
          }}
          onMouseEnter={() => setActiveSection('events')}
        >
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-4 flex items-center gap-2">
            <span aria-hidden>🎭</span>
            Events in {context?.cityName || context?.countryName || 'your area'}
          </h2>
          {filteredEvents.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredEvents.map((ev) => (
                <EventCard key={ev.id} event={ev} />
              ))}
            </div>
          ) : (
            <Card padding="lg">
              <p className="text-[#6b7280]">
                No upcoming events matched your filters. Try adjusting or clearing filters.
              </p>
            </Card>
          )}
        </section>
      </div>

      {/* Country fallback notice */}
      {context?.cityName &&
        payload?.resources &&
        payload.resources.length > 0 &&
        !payload.resources.some(
          (r) => (r.cityName || '').toLowerCase() === (context.cityName || '').toLowerCase()
        ) && (
          <Card padding="md" className="mt-6 border-[#fef3c7] bg-[#fffbeb]">
            <p className="text-sm text-[#92400e]">
              Showing country-wide resources because city-specific content is limited.
            </p>
          </Card>
        )}
    </AppShell>
  );
};

function ResourceSection({
  sectionId,
  label,
  icon,
  resources,
}: {
  sectionId: string;
  label: string;
  icon: string;
  resources: PublicResource[];
  context?: ResourceContext | null;
}) {
  if (resources.length === 0 && sectionId !== 'overview') return null;

  return (
    <Card padding="lg">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl" aria-hidden>
          {icon}
        </span>
        <h2 className="text-lg font-semibold text-[#0b2b43]">{label}</h2>
      </div>
      {resources.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {resources.map((r) => (
            <ResourceCard key={r.id} resource={r} />
          ))}
        </div>
      ) : (
        sectionId === 'overview' && (
          <p className="text-[#6b7280] text-sm">
            Explore the sections below for practical guidance on your relocation.
          </p>
        )
      )}
    </Card>
  );
}

function ResourceCard({ resource }: { resource: PublicResource }) {
  const url = resource.externalUrl || resource.bookingUrl || '#';

  return (
    <div className="p-4 border border-[#e2e8f0] rounded-lg hover:border-[#94a3b8] hover:shadow-sm transition-all">
      {url && url !== '#' ? (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="block"
        >
          <div className="font-medium text-[#0b2b43]">{resource.title}</div>
          {resource.summary && (
            <div className="text-xs text-[#6b7280] mt-1 line-clamp-2">
              {resource.summary}
            </div>
          )}
          {resource.priceRangeText && (
            <div className="text-xs text-[#6b7280] mt-1">{resource.priceRangeText}</div>
          )}
          {resource.trustTier && (
            <span className="inline-block mt-2 text-[10px] px-1.5 py-0.5 rounded bg-[#f1f5f9] text-[#64748b]">
              {resource.trustTier}
            </span>
          )}
          <span className="text-xs text-[#1d4ed8] mt-2 inline-block">View details →</span>
        </a>
      ) : (
        <>
          <div className="font-medium text-[#0b2b43]">{resource.title}</div>
          {resource.summary && (
            <div className="text-xs text-[#6b7280] mt-1 line-clamp-2">
              {resource.summary}
            </div>
          )}
          {resource.priceRangeText && (
            <div className="text-xs text-[#6b7280] mt-1">{resource.priceRangeText}</div>
          )}
          {resource.isFamilyFriendly && (
            <span className="text-xs text-[#059669] mt-1 inline-block">Family-friendly</span>
          )}
        </>
      )}
    </div>
  );
}

function EventCard({ event }: { event: PublicEvent }) {
  const url = event.bookingUrl || event.externalUrl;

  return (
    <Card padding="md" className="flex flex-col h-full">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-xs px-2 py-0.5 rounded-full bg-[#eef4f8] text-[#0b2b43]">
          {EVENT_TYPE_LABELS[event.eventType] || event.eventType}
        </span>
        {event.isFamilyFriendly && (
          <span className="text-xs text-[#059669]">Family-friendly</span>
        )}
        {event.isFree && (
          <span className="text-xs px-2 py-0.5 rounded bg-[#dcfce7] text-[#166534]">Free</span>
        )}
      </div>
      <h3 className="font-medium text-[#0b2b43]">{event.title}</h3>
      {event.description && (
        <p className="text-sm text-[#6b7280] mt-1 line-clamp-2">{event.description}</p>
      )}
      {event.venueName && (
        <p className="text-xs text-[#94a3b8] mt-1">{event.venueName}</p>
      )}
      <p className="text-sm font-medium text-[#0b2b43] mt-2">
        {formatEventDate(event.startDatetime)}
      </p>
      {event.priceText && !event.isFree && (
        <p className="text-sm text-[#6b7280]">{event.priceText}</p>
      )}
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-block text-sm text-[#1d4ed8] hover:underline"
        >
          {event.bookingUrl ? 'Book' : 'More info'} →
        </a>
      )}
    </Card>
  );
}
