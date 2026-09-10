import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Card, Button, Input, Alert } from '../../components/antigravity';
import { loadErrorMessage } from '../../components/LoadErrorBanner';
import { resourcesAPI } from '../../api/client';
import { getCountryName } from '../../utils/countries';
import type {
  ResourcesPagePayload,
  PublicResource,
  PublicEvent,
  RecommendationGroup,
  CityActivity,
  SettlingGuide,
} from '../../types';

export const SECTIONS = [
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

export const EVENT_TYPE_LABELS: Record<string, string> = {
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

export type ResourcesFilters = {
  city: string;
  family: string;
  childAge: string;
  budget: string;
  category: string;
  language: string;
  free: string;
  familyFriendly: string;
  weekendOnly: string;
  eventType: string;
  search: string;
};

export const EMPTY_RESOURCES_FILTERS: ResourcesFilters = {
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

export type ResourcesPageContentProps = {
  payload: ResourcesPagePayload;
  filters: ResourcesFilters;
  updateFilters: (next: Partial<ResourcesFilters>) => void;
  clearFilters: () => void;
};

/**
 * Shared rendering body for the Resources experience.
 *
 * Used by both the employee Resources page (assignment-derived context) and
 * the HR Resources preview (HR-chosen destination + persona). The component
 * is pure: parent owns payload fetching and filter state.
 */
export const ResourcesPageContent: React.FC<ResourcesPageContentProps> = ({
  payload,
  filters,
  updateFilters,
  clearFilters,
}) => {
  const [activeSection, setActiveSection] = useState('overview');
  // M-07b (AIQ-1262): the 9 filter dropdowns are collapsed behind a "Filters" toggle
  // by default so the page leads with content. Active (non-search) filters surface as
  // dismissible chips + a count on the toggle.
  const [showFilters, setShowFilters] = useState(false);
  const activeFilterChips = useMemo(() => {
    const labels: Partial<Record<keyof ResourcesFilters, string>> = {
      city: 'City', family: 'Family', childAge: 'Child age', budget: 'Budget',
      category: 'Category', free: 'Price', familyFriendly: 'Family-friendly',
      eventType: 'Event type', weekendOnly: 'When',
    };
    return (Object.keys(labels) as (keyof ResourcesFilters)[])
      .filter((k) => filters[k])
      .map((k) => ({ key: k, label: labels[k]! }));
  }, [filters]);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  // AIQ-1581: city-level "things to do" feed. Generated on the fly from the
  // (non-personal) city + country via the LLM — replaces the old dead-end
  // "city items are thin" banner.
  const [cityActivities, setCityActivities] = useState<CityActivity[]>([]);
  const [cityActivitiesLoading, setCityActivitiesLoading] = useState(false);
  const [cityActivitiesError, setCityActivitiesError] = useState<string | null>(null);

  const context = payload?.context ?? null;
  // AIQ-1272: fall back to the resolved full country name when the API didn't
  // send countryName, so the hero never shows a bare ISO code.
  const destCountryName = context ? (context.countryName || getCountryName(context.countryCode)) : null;
  const destination = context
    ? [context.cityName, destCountryName].filter(Boolean).join(', ') || destCountryName || 'Your destination'
    : null;

  const cityName = context?.cityName ?? '';
  const countryForActivities = destCountryName ?? '';
  useEffect(() => {
    // Only fetch when we have a city — this feed is city-level by design.
    if (!cityName) {
      setCityActivities([]);
      setCityActivitiesError(null);
      return;
    }
    let cancelled = false;
    setCityActivitiesLoading(true);
    setCityActivitiesError(null);
    resourcesAPI
      .getCityActivities(cityName, countryForActivities)
      .then((list) => {
        if (!cancelled) {
          setCityActivities(list);
          setCityActivitiesError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setCityActivities([]);
          setCityActivitiesError(loadErrorMessage(e, 'Could not load city activities.'));
        }
      })
      .finally(() => {
        if (!cancelled) setCityActivitiesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cityName, countryForActivities]);

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
  const settlingGuide = payload?.settlingGuide;
  const showSettlingGuide = Boolean(
    settlingGuide?.culturalAwareness?.intro ||
      settlingGuide?.culturalAwareness?.tips?.length ||
      settlingGuide?.culturalAwareness?.workCulture?.length ||
      settlingGuide?.firstSteps?.length ||
      settlingGuide?.community?.overview ||
      settlingGuide?.community?.groups?.length ||
      settlingGuide?.practicalTips?.length,
  );

  const scrollToSection = (id: string) => {
    setActiveSection(id);
    const el = sectionRefs.current[id];
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <>
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
          Resources matched to your profile and destination.
        </p>
        {hints.priorities?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs text-white/80">Priorities:</span>
            {hints.priorities.slice(0, 5).map((p) => (
              <span key={p} className="text-xs px-2 py-0.5 rounded-full bg-white/20">
                {String(p).replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}
        {hints.recommendations?.length > 0 && (
          <div className="mt-3 p-3 rounded-lg bg-white/10">
            <div className="text-xs font-medium text-white/90 mb-1">Suggested next:</div>
            <ul className="text-sm text-white/90 space-y-1">
              {hints.recommendations.map((r) => (
                <li key={r}>• {r}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'First steps', icon: '📋', sectionId: showSettlingGuide ? 'settling-first-steps' : 'admin_essentials' },
            { label: 'Housing', icon: '🏠', sectionId: 'housing' },
            { label: 'Healthcare', icon: '🏥', sectionId: 'healthcare' },
            ...(context?.hasChildren
              ? [{ label: 'Schools', icon: '🎓', sectionId: 'schools' }]
              : [{ label: 'Community', icon: '🤝', sectionId: showSettlingGuide ? 'settling-community' : 'community' }]),
          ].map(({ label, icon, sectionId }) => (
            <Button unstyled
              key={label}
              type="button"
              onClick={() => scrollToSection(sectionId)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-left text-sm"
            >
              <span aria-hidden>{icon}</span>
              {label}
            </Button>
          ))}
        </div>
      </section>

      {/* fix: IDR-260909-D201 — settle-in guide so /resources is never a blank catalog shell */}
      {showSettlingGuide && settlingGuide && <SettlingGuidePanel guide={settlingGuide} sectionRefs={sectionRefs} />}

      {/* Recommendations */}
      {(recommended.recommendedForYou?.length > 0 ||
        recommended.firstSteps?.length > 0 ||
        recommended.familyEssentials?.length > 0 ||
        recommended.thisWeekend?.length > 0) && (
        <Card padding="lg" className="mb-6">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Suggested for you</h2>
          <div className="space-y-4">
            {/* M-07a (AIQ-1265): the "Top picks" section duplicated the same items as
                "First steps" below — removed it; First steps is the canonical list. */}
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
                <h3 className="text-sm font-medium text-[#64748b] mb-2">Family essentials</h3>
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
                  This week ({context?.cityName || 'local'})
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

      {/* Filters — collapsed behind a toggle by default (M-07b / AIQ-1262). */}
      <Card padding="md" className="mb-6">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-40 sm:w-48">
            <Input
              placeholder="Search resources"
              value={filters.search}
              onChange={(value) => updateFilters({ search: value })}
            />
          </div>
          <Button
            variant="secondary"
            onClick={() => setShowFilters((v) => !v)}
            aria-expanded={showFilters}
          >
            Filters{activeFilterChips.length > 0 ? ` (${activeFilterChips.length})` : ''} {showFilters ? '▴' : '▾'}
          </Button>
          {activeFilterChips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={() => updateFilters({ [chip.key]: '' } as Partial<ResourcesFilters>)}
              className="inline-flex items-center gap-1 rounded-full bg-[#e2e8f0] px-3 py-1 text-xs text-[#334155] hover:bg-[#cbd5e1]"
            >
              {chip.label}
              <span aria-hidden>×</span>
              <span className="sr-only">Remove {chip.label} filter</span>
            </button>
          ))}
        </div>
        {showFilters && (
          <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-[#e2e8f0] pt-3">
            <select
              value={filters.city}
              onChange={(e) => updateFilters({ city: e.target.value })}
              className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">City</option>
              {context?.cityName && <option value={context.cityName}>{context.cityName}</option>}
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
              <option value="">Price</option>
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
              {Object.entries(EVENT_TYPE_LABELS)
                .sort(([, a], [, b]) => a.localeCompare(b))
                .map(([v, l]) => (
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
              <option value="">When</option>
              <option value="true">Weekend only</option>
            </select>
            {(Object.values(filters).some(Boolean) && (
              <Button variant="secondary" onClick={clearFilters}>
                Clear filters
              </Button>
            )) || null}
          </div>
        )}
      </Card>

      {/* Section nav */}
      <nav
        className="flex gap-1 overflow-x-auto pb-2 mb-6 border-b border-[#e2e8f0] -mx-2 px-2"
        aria-label="Resource sections"
      >
        {SECTIONS.map((s) => (
          <Button unstyled
            key={s.id}
            type="button"
            onClick={() => scrollToSection(s.id)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium whitespace-nowrap transition-colors ${
              activeSection === s.id
                ? 'bg-[#0b2b43] text-white'
                : 'bg-[#f8fafc] text-[#4b5563] hover:bg-[#eef2f7]'
            }`}
          >
            <span className="mr-1" aria-hidden>
              {s.icon}
            </span>
            {s.label}
          </Button>
        ))}
      </nav>

      {/* Content modules */}
      <div className="space-y-8">
        {/* NAV-002: when no resource section has any content, show a single empty
            state instead of section shells. Otherwise hide every empty section
            (including 'overview') rather than rendering an empty header. */}
        {SECTIONS.filter((s) => s.id !== 'events').every(
          (s) => (resourcesBySection[s.id]?.length ?? 0) === 0,
        ) && !showSettlingGuide && (
          <Card padding="lg">
            <p className="text-[#6b7280] text-sm">No resources available for this destination yet.</p>
          </Card>
        )}
        {SECTIONS.filter((s) => s.id !== 'events').map((section) => {
          const items = resourcesBySection[section.id] ?? [];
          if (items.length === 0) return null;
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
              <p className="text-[#6b7280]">No events match these filters. Clear filters or widen the search.</p>
            </Card>
          )}
        </section>

        {/* Things to do — AIQ-1581. City-level activity suggestions replace the
            old "city items are thin" dead-end banner. Only rendered while
            loading or when we actually have suggestions. */}
        {cityName && (cityActivitiesLoading || cityActivitiesError || cityActivities.length > 0) && (
          <section aria-labelledby="things-to-do-heading">
            <h2
              id="things-to-do-heading"
              className="text-lg font-semibold text-navy-800 mb-1 flex items-center gap-2"
            >
              <span aria-hidden>🧭</span>
              Things to do in {cityName}
            </h2>
            <p className="text-sm text-slate-500 mb-4">
              Ideas to help you settle in and explore. AI-generated suggestions — verify details locally.
            </p>
            {cityActivitiesLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[0, 1, 2].map((i) => (
                  <Card key={i} padding="md" className="animate-pulse">
                    <div className="h-4 w-2/3 rounded bg-slate-200 mb-2" />
                    <div className="h-3 w-full rounded bg-slate-100 mb-1" />
                    <div className="h-3 w-4/5 rounded bg-slate-100" />
                  </Card>
                ))}
              </div>
            ) : cityActivitiesError ? (
              <Alert variant="error">{cityActivitiesError}</Alert>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {cityActivities.map((a, i) => (
                  <CityActivityCard key={`${a.title}-${i}`} activity={a} />
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </>
  );
};

function SettlingGuidePanel({
  guide,
  sectionRefs,
}: {
  guide: SettlingGuide;
  sectionRefs: React.MutableRefObject<Record<string, HTMLElement | null>>;
}) {
  const culture = guide.culturalAwareness;
  return (
    <div className="space-y-4 mb-6">
      {(culture.intro || culture.tips.length > 0 || culture.workCulture.length > 0) && (
        <Card padding="lg">
          <h2 className="text-lg font-semibold text-navy-800 mb-2">Cultural awareness</h2>
          {culture.intro && <p className="text-sm text-slate-600 mb-3">{culture.intro}</p>}
          {culture.tips.length > 0 && (
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-600">
              {culture.tips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          )}
          {culture.workCulture.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-slate-500 mb-2">How people work here</h3>
              <ul className="list-disc pl-5 space-y-1 text-sm text-slate-600">
                {culture.workCulture.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
      {guide.firstSteps.length > 0 && (
        <section
          ref={(el) => {
            sectionRefs.current['settling-first-steps'] = el;
            sectionRefs.current['admin_essentials'] = el;
          }}
        >
          <Card padding="lg">
            <h2 className="text-lg font-semibold text-navy-800 mb-3">First steps to settle in</h2>
            <ol className="space-y-3">
              {guide.firstSteps.map((step, i) => (
                <li key={step.title} className="text-sm">
                  <div className="font-medium text-navy-800">
                    {i + 1}. {step.title}
                  </div>
                  {step.timeline && <p className="text-slate-500 mt-0.5">{step.timeline}</p>}
                  {step.url && (
                    <a
                      href={step.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-accent-600 hover:text-accent-700 text-xs mt-1 inline-block"
                    >
                      Official source
                    </a>
                  )}
                </li>
              ))}
            </ol>
          </Card>
        </section>
      )}
      {(guide.community.overview || guide.community.groups.length > 0) && (
        <section
          ref={(el) => {
            sectionRefs.current['settling-community'] = el;
            sectionRefs.current['community'] = el;
          }}
        >
          <Card padding="lg">
            <h2 className="text-lg font-semibold text-navy-800 mb-2">Communities</h2>
            {guide.community.overview && (
              <p className="text-sm text-slate-600 mb-3">{guide.community.overview}</p>
            )}
            {guide.community.groups.length > 0 && (
              <ul className="space-y-2">
                {guide.community.groups.map((g) => (
                  <li key={g.title} className="text-sm">
                    {g.url ? (
                      <a
                        href={g.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-accent-600 hover:text-accent-700"
                      >
                        {g.title}
                      </a>
                    ) : (
                      <span className="font-medium text-navy-800">{g.title}</span>
                    )}
                    {g.description && <p className="text-slate-500">{g.description}</p>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </section>
      )}
      {(guide.practicalTips.length > 0 || guide.emergency) && (
        <Card padding="lg">
          <h2 className="text-lg font-semibold text-navy-800 mb-2">Practical tips</h2>
          {guide.emergency && (
            <p className="text-sm text-slate-600 mb-2">
              Emergency number: <span className="font-medium text-navy-800">{guide.emergency}</span>
            </p>
          )}
          {guide.practicalTips.length > 0 && (
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-600">
              {guide.practicalTips.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}

function CityActivityCard({ activity }: { activity: CityActivity }) {
  return (
    <Card padding="md" className="flex flex-col h-full">
      {activity.category && (
        <span className="self-start text-xs px-2 py-0.5 rounded-full bg-accent-50 text-accent-700 mb-2">
          {activity.category.replace(/_/g, ' ')}
        </span>
      )}
      <h3 className="font-medium text-navy-800">{activity.title}</h3>
      {activity.description && (
        <p className="text-sm text-slate-600 mt-1">{activity.description}</p>
      )}
    </Card>
  );
}

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
          <p className="text-[#6b7280] text-sm">Use the tabs below to browse by topic.</p>
        )
      )}
    </Card>
  );
}

// NAV-002: trust-tier → labelled, colored badge (verified=teal, community=amber,
// unverified=gray). Unknown/absent tiers render nothing.
const TRUST_TIER_BADGE: Record<string, { label: string; cls: string }> = {
  // 3.42:1 on this tint — badge TEXT, so it needs 4.5:1. accent-700 gives 6.62:1.
  verified: { label: 'Verified', cls: 'bg-[#e0f2f1] text-[#105d5b]' },
  community: { label: 'Community', cls: 'bg-[#fef3c7] text-[#92400e]' },
  unverified: { label: 'Unverified', cls: 'bg-[#f1f5f9] text-[#64748b]' },
};

// NAV-002: local relative-time formatter (no external library).
function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`;
  const years = Math.floor(days / 365);
  return `${years} year${years === 1 ? '' : 's'} ago`;
}

function ResourceCard({ resource }: { resource: PublicResource }) {
  const url = resource.externalUrl || resource.bookingUrl || '#';
  const hasUrl = Boolean(url && url !== '#');
  const tier = resource.trustTier ? TRUST_TIER_BADGE[resource.trustTier] : null;
  const updatedAt = resource.updated_at;

  // Curation signals (trust tier + last-updated) shown on both link and non-link cards.
  const meta =
    tier || updatedAt ? (
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {tier && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${tier.cls}`}>{tier.label}</span>
        )}
        {updatedAt && <span className="text-xs text-slate-500">Updated {formatRelativeTime(updatedAt)}</span>}
      </div>
    ) : null;

  return (
    <div className="p-4 border border-[#e2e8f0] rounded-lg hover:border-[#94a3b8] hover:shadow-sm transition-all">
      {hasUrl ? (
        <a href={url} target="_blank" rel="noreferrer" className="block">
          <div className="font-medium text-[#0b2b43]">{resource.title}</div>
          {resource.summary && (
            <div className="text-xs text-[#6b7280] mt-1 line-clamp-2">{resource.summary}</div>
          )}
          {resource.priceRangeText && (
            <div className="text-xs text-[#6b7280] mt-1">{resource.priceRangeText}</div>
          )}
          {meta}
          <span className="text-xs text-[#1d4ed8] mt-2 inline-block">Open</span>
        </a>
      ) : (
        <>
          <div className="font-medium text-[#0b2b43]">{resource.title}</div>
          {resource.summary && (
            <div className="text-xs text-[#6b7280] mt-1 line-clamp-2">{resource.summary}</div>
          )}
          {resource.priceRangeText && (
            <div className="text-xs text-[#6b7280] mt-1">{resource.priceRangeText}</div>
          )}
          {resource.isFamilyFriendly && (
            <span className="text-xs text-[#059669] mt-1 inline-block">Family-friendly</span>
          )}
          {meta}
        </>
      )}
      {/* NAV-002: unobtrusive stale-link report, outside the anchor, only when a URL exists. */}
      {hasUrl && (
        <a
          href={`mailto:support@relopass.com?subject=Stale+link+report&body=${encodeURIComponent(
            `${resource.title} — ${url}`,
          )}`}
          className="text-xs text-slate-500 hover:text-[#64748b] mt-1 inline-block"
        >
          Report stale link
        </a>
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
      {event.venueName && <p className="text-xs text-slate-500 mt-1">{event.venueName}</p>}
      <p className="text-sm font-medium text-[#0b2b43] mt-2">{formatEventDate(event.startDatetime)}</p>
      {event.priceText && !event.isFree && <p className="text-sm text-[#6b7280]">{event.priceText}</p>}
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-block text-sm text-[#1d4ed8] hover:underline"
        >
          Open
        </a>
      )}
    </Card>
  );
}
