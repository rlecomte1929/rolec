import React, { useEffect, useState, useMemo } from 'react';
import { AppShell } from '../components/AppShell';
import { Card, Button, Input } from '../components/antigravity';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { resourcesAPI } from '../api/client';

const SECTION_ICONS: Record<string, string> = {
  welcome: '👋',
  admin_essentials: '📋',
  housing: '🏠',
  schools: '🎓',
  healthcare: '🏥',
  transport: '🚇',
  daily_life: '🛒',
  community: '🤝',
  culture_leisure: '🎭',
  nature: '🏔️',
  cost_of_living: '💰',
  safety: '🛡️',
};

const TABS = [
  { key: 'overview', label: 'Overview', sections: ['welcome', 'cost_of_living', 'safety'] },
  { key: 'admin_essentials', label: 'Admin Essentials', sections: ['admin_essentials'] },
  { key: 'housing', label: 'Housing', sections: ['housing'] },
  { key: 'schools', label: 'Schools', sections: ['schools'] },
  { key: 'healthcare', label: 'Healthcare', sections: ['healthcare'] },
  { key: 'transport', label: 'Transport', sections: ['transport'] },
  { key: 'daily_life', label: 'Daily Life', sections: ['daily_life'] },
  { key: 'community', label: 'Community', sections: ['community'] },
  { key: 'events', label: 'Events', sections: ['culture_leisure'] },
  { key: 'nature', label: 'Nature', sections: ['nature'] },
];

export const Resources: React.FC = () => {
  const { assignmentId, isLoading: assignmentLoading } = useEmployeeAssignment();
  const [profile, setProfile] = useState<Record<string, any> | null>(null);
  const [sections, setSections] = useState<Array<{ key: string; title: string; content: any }>>([]);
  const [hints, setHints] = useState<{ priorities: string[]; recommendations: string[] }>({ priorities: [], recommendations: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [filters, setFilters] = useState<Record<string, string>>({
    city: '',
    family_type: '',
    budget: '',
    category: '',
    indoor_outdoor: '',
    free_paid: '',
    weekday_weekend: '',
  });
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!assignmentId || assignmentLoading) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    resourcesAPI
      .getCountryResources(assignmentId, Object.fromEntries(Object.entries(filters).filter(([, v]) => v)))
      .then((res) => {
        setProfile(res.profile);
        setSections(res.sections);
        setHints(res.hints || { priorities: [], recommendations: [] });
      })
      .catch((err: any) => {
        setError(err?.response?.data?.detail || err?.message || 'Unable to load resources');
        setProfile(null);
        setSections([]);
      })
      .finally(() => setLoading(false));
  }, [assignmentId, assignmentLoading, JSON.stringify(filters)]);

  const destination = profile?.destination_country
    ? [profile.destination_city, profile.destination_country].filter(Boolean).join(', ')
    : null;

  const visibleSections = useMemo(() => {
    const tab = TABS.find((t) => t.key === activeTab);
    if (!tab) return sections;
    return sections.filter((s) => tab.sections.includes(s.key));
  }, [sections, activeTab]);

  const filteredSections = useMemo(() => {
    if (!search.trim()) return visibleSections;
    const q = search.toLowerCase();
    return visibleSections.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        JSON.stringify(s.content).toLowerCase().includes(q)
    );
  }, [visibleSections, search]);

  if (assignmentLoading || (loading && !profile)) {
    return (
      <AppShell title="Resources" subtitle="Practical tips for your relocation.">
        <div className="text-center py-12 text-[#6b7280]">Loading resources…</div>
      </AppShell>
    );
  }

  if (!assignmentId) {
    return (
      <AppShell title="Resources" subtitle="Practical tips for your relocation.">
        <Card padding="lg">
          <p className="text-[#4b5563]">
            Complete the intake wizard and select a destination to see country-specific resources.
          </p>
        </Card>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell title="Resources" subtitle="Practical tips for your relocation.">
        <Card padding="lg" className="border-red-200 bg-red-50">
          <p className="text-red-700">{error}</p>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Resources" subtitle="Practical, structured information for your relocation.">
      {/* Hero */}
      <div className="rounded-xl bg-gradient-to-br from-[#0b2b43] to-[#1e4a6e] text-white p-6 mb-6">
        <h1 className="text-2xl font-bold mb-1">
          Welcome to {destination || 'Your Destination'}
        </h1>
        <p className="text-white/90 text-sm">
          {profile?.has_children && 'Family-focused • '}
          {profile?.relocation_type && `${profile.relocation_type} assignment • `}
          Practical guidance for your first weeks
        </p>
        {hints.priorities?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs text-white/80">Priorities:</span>
            {hints.priorities.slice(0, 5).map((p) => (
              <span key={p} className="text-xs px-2 py-0.5 rounded-full bg-white/20">
                {p.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}
        {hints.recommendations?.length > 0 && (
          <div className="mt-3 p-3 rounded-lg bg-white/10">
            <div className="text-xs font-medium text-white/90 mb-1">Based on your profile we recommend:</div>
            <ul className="text-sm text-white/90 space-y-1">
              {hints.recommendations.map((r) => (
                <li key={r}>• {r}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Filters */}
      <Card padding="md" className="mb-6">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-48">
            <Input placeholder="Search..." value={search} onChange={setSearch} />
          </div>
          <select
            value={filters.city}
            onChange={(e) => setFilters((f) => ({ ...f, city: e.target.value }))}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm"
          >
            <option value="">City</option>
            <option value={profile?.destination_city || ''}>{profile?.destination_city || '—'}</option>
          </select>
          <select
            value={filters.family_type}
            onChange={(e) => setFilters((f) => ({ ...f, family_type: e.target.value }))}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Family type</option>
            <option value="single">Single</option>
            <option value="couple">Couple</option>
            <option value="family">Family</option>
          </select>
          <select
            value={filters.budget}
            onChange={(e) => setFilters((f) => ({ ...f, budget: e.target.value }))}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Budget</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
          <select
            value={filters.category}
            onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}
            className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Category</option>
            <option value="admin">Admin</option>
            <option value="housing">Housing</option>
            <option value="schools">Schools</option>
            <option value="health">Healthcare</option>
            <option value="transport">Transport</option>
            <option value="community">Community</option>
            <option value="culture">Culture</option>
            <option value="nature">Nature</option>
          </select>
        </div>
      </Card>

      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto pb-2 mb-4 border-b border-[#e2e8f0]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium whitespace-nowrap transition-colors ${
              activeTab === tab.key
                ? 'bg-[#0b2b43] text-white'
                : 'bg-[#f8fafc] text-[#4b5563] hover:bg-[#eef2f7]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sections */}
      <div className="space-y-6">
        {filteredSections.map((section) => (
          <ResourceSection key={section.key} section={section} profile={profile} />
        ))}
        {filteredSections.length === 0 && (
          <Card padding="lg">
            <p className="text-[#6b7280]">No matching content. Try adjusting your filters or search.</p>
          </Card>
        )}
      </div>
    </AppShell>
  );
};

function ResourceSection({
  section,
  profile,
}: {
  section: { key: string; title: string; content: any };
  profile: Record<string, any> | null;
}) {
  const icon = SECTION_ICONS[section.key] || '📋';
  const content = section.content || {};
  const topics = content.topics || [];
  const items = content.items || content.platforms || content.groups || [];

  return (
    <Card padding="lg">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-2xl" aria-hidden>{icon}</span>
        <h2 className="text-lg font-semibold text-[#0b2b43]">{section.title}</h2>
      </div>
      {content.intro && <p className="text-[#4b5563] text-sm mb-4">{content.intro}</p>}
      {content.overview && <p className="text-[#4b5563] text-sm mb-4">{content.overview}</p>}

      {topics.length > 0 && (
        <div className="space-y-3">
          {topics.map((t: any, i: number) => (
            <div key={i} className="flex justify-between items-start gap-4 p-3 rounded-lg bg-[#f8fafc]">
              <div>
                <div className="font-medium text-[#0b2b43]">{t.title}</div>
                {t.timeline && <div className="text-xs text-[#6b7280]">Timeline: {t.timeline}</div>}
              </div>
              {t.link && (
                <a href={t.link} target="_blank" rel="noreferrer" className="text-sm text-[#1d4ed8] hover:underline">
                  Official link
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {content.cultural_tips && (
        <div className="mt-4">
          <div className="text-sm font-medium text-[#0b2b43] mb-2">Cultural tips</div>
          <ul className="list-disc list-inside text-sm text-[#4b5563] space-y-1">
            {content.cultural_tips.map((tip: string, i: number) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </div>
      )}

      {content.school_types && (
        <div className="mt-4">
          <div className="text-sm font-medium text-[#0b2b43] mb-2">School types</div>
          <div className="flex flex-wrap gap-2">
            {content.school_types.map((t: string) => (
              <span key={t} className="px-3 py-1 rounded-full bg-[#eef4f8] text-sm text-[#0b2b43]">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {content.emergency && (
        <div className="mt-4 p-3 rounded-lg bg-[#fef2f2]">
          <span className="text-sm font-medium text-[#7a2a2a]">Emergency: </span>
          <span className="text-sm text-[#7a2a2a]">{content.emergency}</span>
        </div>
      )}

      {items.length > 0 && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map((item: any, i: number) => (
            <div key={i} className="p-3 border border-[#e2e8f0] rounded-lg">
              <div className="font-medium text-[#0b2b43]">{item.title || item.name}</div>
              {item.description && <div className="text-xs text-[#6b7280] mt-1">{item.description}</div>}
              {item.url && (
                <a href={item.url} target="_blank" rel="noreferrer" className="text-xs text-[#1d4ed8] hover:underline mt-2 inline-block">
                  Visit
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {content.tips && (
        <div className="mt-4">
          <ul className="list-disc list-inside text-sm text-[#4b5563] space-y-1">
            {content.tips.map((tip: string, i: number) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </div>
      )}

      {content.items && Array.isArray(content.items) && section.key === 'cost_of_living' && (
        <div className="mt-4 space-y-2">
          {content.items.map((item: any, i: number) => (
            <div key={i} className="flex justify-between text-sm">
              <span className="text-[#4b5563]">{item.label}</span>
              <span className="font-medium text-[#0b2b43]">{item.value}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
