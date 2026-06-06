import { useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { AppShell } from '../../../components/AppShell';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Source {
  id: string;
  name: string;
  url: string;
  init: string;
  verified: boolean;
  live: boolean;
  fetched: string;
  items: number;
}

interface Requirement {
  id: number;
  t: string;
  cat: string;
  owner: string;
  time: string;
  conf: number;
  src: string;
  deps: number[];
  conditional?: string;
}

interface LogEntry {
  ts: string;
  msg: Array<string | { h?: string; ok?: string; warn?: string }>;
}

interface TimelinePhase {
  wk: string;
  t: string;
  reqs: number[];
  color: 'accent' | 'teal' | 'warning' | 'success';
}

type DiscoveryTab = 'requirements' | 'timeline' | 'sources';

// ─── Mock data ────────────────────────────────────────────────────────────────

const SOURCES: Source[] = [
  { id: 'udi',    name: 'UDI — Norwegian Directorate of Immigration', url: 'udi.no',            init: 'UDI', verified: true, live: true,  fetched: 'just now',  items: 18 },
  { id: 'skatt',  name: 'Skatteetaten — Norwegian Tax Administration', url: 'skatteetaten.no',  init: 'SK',  verified: true, live: true,  fetched: '12s ago',   items: 6  },
  { id: 'eu',     name: 'EU/EEA Free Movement Portal',                url: 'eu.europa.eu',      init: 'EU',  verified: true, live: false, fetched: '2 min ago', items: 9  },
  { id: 'fr',     name: 'France Diplomatie — Civil Documents',        url: 'diplomatie.gouv.fr', init: 'FR', verified: true, live: false, fetched: '4 min ago', items: 7  },
  { id: 'arb',    name: 'Arbeidstilsynet — Labour Inspectorate',      url: 'arbeidstilsynet.no', init: 'AT', verified: true, live: false, fetched: '5 min ago', items: 4  },
  { id: 'aurora', name: 'Aurora Energy — HR Policy Engine',           url: 'internal',           init: 'AE', verified: true, live: false, fetched: '7 min ago', items: 3  },
];

const REQUIREMENTS: Requirement[] = [
  { id: 1,  t: 'Employer sponsorship declaration to UDI',        cat: 'Visa',    owner: 'Employer',  time: '1–2 wks', conf: 99,  src: 'udi',   deps: [] },
  { id: 2,  t: 'Skilled worker permit application (UDI online)', cat: 'Visa',    owner: 'Employee',  time: '3–5 wks', conf: 98,  src: 'udi',   deps: [1] },
  { id: 3,  t: 'Apostilled birth certificate (France)',          cat: 'Civil',   owner: 'Employee',  time: '2–3 wks', conf: 96,  src: 'fr',    deps: [] },
  { id: 4,  t: 'Apostilled marriage certificate (France)',       cat: 'Civil',   owner: 'Employee',  time: '2–3 wks', conf: 95,  src: 'fr',    deps: [] },
  { id: 5,  t: 'Certified translation of civil documents',       cat: 'Civil',   owner: 'Vendor',    time: '1 wk',    conf: 93,  src: 'fr',    deps: [3, 4] },
  { id: 6,  t: 'Proof of housing in Stavanger',                  cat: 'Housing', owner: 'Employee',  time: '2–4 wks', conf: 90,  src: 'udi',   deps: [2] },
  { id: 7,  t: 'Tuberculosis test (children only)',              cat: 'Health',  owner: 'Employee',  time: '1 wk',    conf: 88,  src: 'udi',   deps: [], conditional: 'kids' },
  { id: 8,  t: 'D-number registration (Skatteetaten)',           cat: 'Tax',     owner: 'Employee',  time: '1–2 wks', conf: 97,  src: 'skatt', deps: [9] },
  { id: 9,  t: 'Police registration on arrival',                 cat: 'Civil',   owner: 'Employee',  time: '1 wk',    conf: 99,  src: 'udi',   deps: [2] },
  { id: 10, t: 'Health insurance (HELFO) registration',          cat: 'Health',  owner: 'Employee',  time: '1 wk',    conf: 92,  src: 'arb',   deps: [8] },
  { id: 11, t: 'School placement for dependents',                cat: 'Family',  owner: 'Employee',  time: '4–8 wks', conf: 84,  src: 'aurora', deps: [6], conditional: 'kids' },
  { id: 12, t: 'Salary threshold confirmation (NOK 635,500)',    cat: 'Visa',    owner: 'Employer',  time: '1 wk',    conf: 100, src: 'udi',   deps: [] },
];

const LOG_ENTRIES: LogEntry[] = [
  { ts: '14:02:11', msg: ['Authenticating ', { h: 'UDI public API' }] },
  { ts: '14:02:13', msg: ['Pulling skilled-worker permit schema… ', { ok: 'OK' }] },
  { ts: '14:02:17', msg: ['Cross-ref ', { h: 'FR↔NO bilateral 2017/8' }] },
  { ts: '14:02:21', msg: ['Detected dependent profile: ', { h: 'partner + 2 kids' }] },
  { ts: '14:02:23', msg: ['Applied conditional rule: ', { h: 'TB test for minors' }] },
  { ts: '14:02:28', msg: ['Compiling requirement graph (', { h: '12 nodes' }, ')'] },
  { ts: '14:02:33', msg: ['Validating salary threshold ', { ok: 'NOK 635,500' }, ' against Aurora contract'] },
  { ts: '14:02:34', msg: ['Threshold met: ', { ok: 'contract €72,000 ≈ NOK 825k' }] },
  { ts: '14:02:38', msg: ['Recommending advisor: ', { h: 'Norwegian mobility law' }] },
  { ts: '14:02:42', msg: [{ warn: 'NOTE' }, ' housing proof typically blocks step 2 by 5–9 days'] },
  { ts: '14:02:45', msg: ['Plan compiled. ', { ok: '47 requirements, 12 documents.' }] },
];

const TIMELINE_PHASES: TimelinePhase[] = [
  { wk: 'wk 1–2',  t: 'Document gathering & employer sponsorship', reqs: [1, 3, 4, 12], color: 'accent' },
  { wk: 'wk 2–4',  t: 'Civil document apostille & translation',    reqs: [3, 4, 5],     color: 'teal' },
  { wk: 'wk 3–7',  t: 'UDI permit application',                    reqs: [2],            color: 'accent' },
  { wk: 'wk 6–9',  t: 'Housing search & confirmation',             reqs: [6],            color: 'teal' },
  { wk: 'wk 8–10', t: 'Health & TB checks (dependents)',           reqs: [7, 10],        color: 'warning' },
  { wk: 'wk 9–11', t: 'Arrival, police registration, tax setup',   reqs: [8, 9, 11],    color: 'success' },
];

// ─── Category colour map ──────────────────────────────────────────────────────

const CAT_COLORS: Record<string, string> = {
  Visa:    'bg-accent-100 text-accent-700',
  Civil:   'bg-blue-100 text-blue-700',
  Housing: 'bg-amber-100 text-amber-700',
  Health:  'bg-green-100 text-green-700',
  Tax:     'bg-cyan-100 text-cyan-700',
  Family:  'bg-pink-100 text-pink-700',
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function DiscoveryBanner() {
  return (
    <div className="flex items-start gap-4 rounded-xl border border-accent-200 bg-accent-50 px-5 py-4 mb-5">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent-600 flex items-center justify-center text-white text-sm">✦</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-gray-900">
          Compiling requirement plan for <span className="text-accent-700">Marc Bouchard</span> ·{' '}
          <span className="text-accent-700">France → Norway</span> · Skilled Worker Residence Permit
        </div>
        <div className="text-xs text-gray-500 mt-0.5">
          Sponsored by Aurora Energy AS. Plan derived from 4 authorities across 2 jurisdictions.
        </div>
      </div>
      <div className="flex gap-6 flex-shrink-0">
        {[
          { k: 'Requirements', v: '47' },
          { k: 'Documents',    v: '12' },
          { k: 'Est. time',    v: '10–14 wks' },
          { k: 'Est. cost',    v: '€680' },
        ].map(({ k, v }) => (
          <div key={k} className="text-center">
            <div className="text-[10px] text-gray-400 font-medium uppercase tracking-wide">{k}</div>
            <div className="text-sm font-bold text-gray-900 tabular-nums">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConfBar({ pct }: { pct: number }) {
  const color = pct >= 95 ? 'bg-green-500' : pct >= 85 ? 'bg-amber-400' : 'bg-red-400';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-gray-500">{pct}%</span>
    </div>
  );
}

function RequirementsTab({
  onShowSources,
}: {
  onShowSources: () => void;
}) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const sourceMap = Object.fromEntries(SOURCES.map((s) => [s.id, s]));

  return (
    <div>
      {/* column header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <span className="text-sm font-semibold text-gray-900">Extracted requirements</span>
          <span className="ml-2 text-xs text-gray-400">{REQUIREMENTS.length} nodes · cross-referenced from 6 official sources</span>
        </div>
        <div className="flex items-center gap-2">
          <Button unstyled
            onClick={onShowSources}
            className="px-3 py-1.5 text-xs font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            View sources
          </Button>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-100 text-accent-700 text-[10px] font-medium">
            ✦ Live
          </span>
        </div>
      </div>

      {/* requirement cards */}
      <div className="grid grid-cols-1 gap-2">
        {REQUIREMENTS.map((r) => {
          const src = sourceMap[r.src];
          const isActive = activeId === r.id;
          return (
            <div
              key={r.id}
              onClick={() => setActiveId(isActive ? null : r.id)}
              className={`flex items-start gap-4 px-4 py-3 rounded-xl border cursor-pointer transition-all ${
                isActive
                  ? 'border-accent-400 bg-accent-50'
                  : 'border-gray-100 bg-white hover:border-gray-200 hover:bg-gray-50'
              }`}
            >
              {/* index */}
              <span className="flex-shrink-0 w-6 text-xs font-mono font-bold text-gray-300 pt-0.5 select-none">
                {String(r.id).padStart(2, '0')}
              </span>

              {/* body */}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-gray-900">{r.t}</div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${CAT_COLORS[r.cat] ?? 'bg-gray-100 text-gray-600'}`}>
                    {r.cat}
                  </span>
                  <span className="text-xs text-gray-400">👤 {r.owner}</span>
                  <span className="text-xs text-gray-400">⏱ {r.time}</span>
                  {r.deps.length > 0 && (
                    <span className="text-xs text-gray-400">
                      depends on {r.deps.map((d) => `#${String(d).padStart(2, '0')}`).join(', ')}
                    </span>
                  )}
                  {r.conditional && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-700">
                      conditional · {r.conditional}
                    </span>
                  )}
                  {src && <span className="text-xs text-gray-300">· {src.init}</span>}
                </div>
              </div>

              {/* confidence */}
              <div className="flex-shrink-0 text-right">
                <ConfBar pct={r.conf} />
                <div className="text-[10px] text-gray-400 mt-0.5">confidence</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TimelineTab() {
  const COLOR_MAP: Record<string, string> = {
    accent:  'bg-accent-500',
    teal:    'bg-teal-500',
    warning: 'bg-amber-400',
    success: 'bg-green-500',
  };

  return (
    <div className="bg-white border border-gray-100 rounded-xl p-5">
      <div className="flex items-center gap-3 mb-5">
        <h3 className="text-sm font-semibold text-gray-900">Compiled plan timeline</h3>
        <span className="px-2 py-0.5 rounded-full border border-gray-200 text-xs text-gray-500">10–14 weeks · 12 documents</span>
      </div>

      <div className="flex flex-col gap-0 divide-y divide-gray-100">
        {TIMELINE_PHASES.map((p, i) => (
          <div key={i} className="grid gap-4 items-center py-3" style={{ gridTemplateColumns: '90px 1fr 160px' }}>
            <span className="font-mono text-xs font-bold text-gray-400">{p.wk}</span>
            <div>
              <div className="text-sm font-semibold text-gray-900">{p.t}</div>
              <div className="text-xs text-gray-400 mt-0.5">
                Requirements: {p.reqs.map((r) => `#${String(r).padStart(2, '0')}`).join(', ')}
              </div>
            </div>
            <div className="w-full h-1.5 rounded-full bg-gray-100 overflow-hidden">
              <div
                className={`h-full rounded-full ${COLOR_MAP[p.color]}`}
                style={{ width: `${(i + 1) * 16}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SourcesTab() {
  return (
    <div className="bg-white border border-gray-100 rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 bg-gray-50">
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Authority</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Domain</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Last fetched</th>
            <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Items</th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {SOURCES.map((s) => (
            <tr key={s.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-md bg-gray-100 flex items-center justify-center text-[10px] font-bold text-gray-600 flex-shrink-0">
                    {s.init}
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-gray-900 leading-tight">{s.name}</div>
                    {s.live && (
                      <span className="inline-flex items-center gap-1 text-[10px] text-accent-600 font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-accent-500 inline-block animate-pulse" />
                        Live
                      </span>
                    )}
                  </div>
                </div>
              </td>
              <td className="px-4 py-3">
                <span className="font-mono text-xs text-gray-500">{s.url}</span>
              </td>
              <td className="px-4 py-3 text-xs text-gray-500">{s.fetched}</td>
              <td className="px-4 py-3 text-right text-xs tabular-nums text-gray-700 font-medium">{s.items}</td>
              <td className="px-4 py-3">
                {s.verified && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-[10px] font-semibold">
                    ✓ Verified
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="px-4 py-2.5 border-t border-gray-100 text-xs text-gray-400 flex items-center gap-2">
        🛡 Sources cached daily · last sync 03:14
      </div>
    </div>
  );
}

function ActivityLog() {
  return (
    <div className="bg-gray-900 rounded-xl p-4 font-mono text-xs leading-relaxed overflow-y-auto max-h-64">
      {LOG_ENTRIES.map((entry, i) => (
        <div
          key={i}
          className={`flex gap-3 py-0.5 ${i === LOG_ENTRIES.length - 1 ? 'text-white' : 'text-gray-400'}`}
        >
          <span className="text-gray-600 flex-shrink-0">{entry.ts}</span>
          <span>
            {entry.msg.map((part, j) => {
              if (typeof part === 'string') return <span key={j}>{part}</span>;
              if (part.h)    return <span key={j} className="text-accent-400 font-semibold">{part.h}</span>;
              if (part.ok)   return <span key={j} className="text-green-400 font-semibold">{part.ok}</span>;
              if (part.warn) return <span key={j} className="text-amber-400 font-semibold">{part.warn}</span>;
              return null;
            })}
          </span>
        </div>
      ))}
      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-700 text-gray-500">
        <span>🗄</span>
        <span>graph compiled · 47 edges · 12 documents</span>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function HrDiscoveryPage() {
  const [tab, setTab] = useState<DiscoveryTab>('requirements');

  const TABS: { id: DiscoveryTab; label: string }[] = [
    { id: 'requirements', label: 'Requirements' },
    { id: 'timeline',     label: 'Timeline' },
    { id: 'sources',      label: 'Sources' },
  ];

  return (
    <AppShell wide>
      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* Page header */}
        <div className="mb-6">
          <div className="text-xs font-semibold text-accent-600 uppercase tracking-widest mb-1">AI Engine</div>
          <div className="flex items-end justify-between gap-4">
            <h1 className="text-2xl font-bold text-gray-900">Requirements</h1>
            <div className="flex items-center gap-2">
              <Button unstyled className="px-3 py-2 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                ⚡ Corridor: <strong>FR → NO</strong>
              </Button>
              <Button unstyled className="px-3 py-2 text-sm font-medium bg-navy-800 text-white rounded-lg hover:bg-navy-900 transition-colors">
                ✦ Re-run discovery
              </Button>
            </div>
          </div>
          <p className="mt-2 text-sm text-gray-500 max-w-3xl">
            ReloPass cross-references official sources, employer policy, and bilateral agreements to compile the requirement graph for each case. Every node carries its source, confidence, and dependencies.
          </p>
        </div>

        {/* Banner */}
        <DiscoveryBanner />

        {/* Toolbar */}
        <div className="flex items-center gap-2 mb-5">
          <div className="flex items-center gap-1 border border-gray-200 rounded-lg p-0.5 bg-gray-50">
            {TABS.map(({ id, label }) => (
              <Button unstyled
                key={id}
                onClick={() => setTab(id)}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  tab === id
                    ? 'bg-white shadow-sm text-gray-900'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {label}
              </Button>
            ))}
          </div>
          <div className="flex-1" />
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-gray-200 text-xs text-gray-500">
            🕐 Last run · 14:02 · 38s
          </span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 text-green-700 text-xs font-medium">
            ✓ All sources verified
          </span>
        </div>

        {/* Tab content */}
        <div className="mb-6">
          {tab === 'requirements' && (
            <RequirementsTab onShowSources={() => setTab('sources')} />
          )}
          {tab === 'timeline' && <TimelineTab />}
          {tab === 'sources' && <SourcesTab />}
        </div>

        {/* Activity log — always visible at bottom */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">AI activity log</span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-[10px] font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" /> compiled
            </span>
          </div>
          <ActivityLog />
        </div>
      </div>
    </AppShell>
  );
  // TODO: replace mock data with real API call:
  // const { data } = await hrAPI.getDiscoveryPlan({ corridorFrom, corridorTo, caseId });
}
