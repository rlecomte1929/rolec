/**
 * DiscoveryScreen.tsx — T06 Discovery Screen (S2) /discovery
 * Employee-facing. Shows requirements from case_discovery_runs.
 * Two tabs: Timeline | Sources
 */

import { useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import type {
  Requirement,
  CaseDiscoveryRun,
  DiscoverySource,
  RequirementCategory,
} from '../../../types/relopass-api-contracts';
import {
  LoadingSpinner,
  EmptyState,
  StatusBadge,
  DateFormatter,
  Pill,
} from '../shared';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface DiscoveryScreenProps {
  discoveryRun: CaseDiscoveryRun | null;
  requirements: Requirement[];
  sources: (DiscoverySource & { requirement_ids: string[] })[];
  onUpload: (requirementId: string) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Category grouping helpers
// ─────────────────────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<RequirementCategory, string> = {
  immigration: 'Immigration',
  employment: 'Employment',
  housing: 'Housing',
  financial: 'Financial',
  tax: 'Tax',
  schooling: 'Schooling',
  medical: 'Medical',
  vehicle: 'Vehicle',
  other: 'Other',
};

const CATEGORY_ICONS: Record<RequirementCategory, string> = {
  immigration: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
  employment: 'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  housing: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  financial: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  tax: 'M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z',
  schooling: 'M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z',
  medical: 'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z',
  vehicle: 'M8 17a2 2 0 100-4 2 2 0 000 4zm8 0a2 2 0 100-4 2 2 0 000 4zM5 9l1.333-4H17.667L19 9H5zm0 0H3m16 0h2',
  other: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
};

function groupByCategory(reqs: Requirement[]): Map<RequirementCategory, Requirement[]> {
  const map = new Map<RequirementCategory, Requirement[]>();
  for (const r of reqs) {
    if (!map.has(r.category)) map.set(r.category, []);
    map.get(r.category)!.push(r);
  }
  return map;
}

// ─────────────────────────────────────────────────────────────────────────────
// Upload Panel (slide-in)
// ─────────────────────────────────────────────────────────────────────────────

interface UploadPanelProps {
  requirement: Requirement | null;
  onClose: () => void;
  onUpload: (requirementId: string) => void;
}

function UploadPanel({ requirement, onClose, onUpload }: UploadPanelProps) {
  if (!requirement) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Upload document for ${requirement.name}`}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      <div
        aria-hidden="true"
        onClick={onClose}
        style={{ position: 'absolute', inset: 0, background: 'var(--overlay)' }}
      />
      <aside
        style={{
          position: 'relative',
          width: '400px',
          maxWidth: '90vw',
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          padding: '24px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>
            Upload Document
          </h2>
          <Button unstyled
            onClick={onClose}
            aria-label="Close panel"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '4px' }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </Button>
        </div>

        <div style={{ padding: '12px', background: 'var(--surface-2)', borderRadius: 'var(--radius-md, 8px)' }}>
          <p style={{ margin: '0 0 4px', fontWeight: 600, fontSize: '14px', color: 'var(--text)' }}>
            {requirement.name}
          </p>
          {requirement.description && (
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              {requirement.description}
            </p>
          )}
        </div>

        {requirement.instructions && (
          <div style={{ padding: '12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md, 8px)' }}>
            <p style={{ margin: '0 0 6px', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Instructions
            </p>
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {requirement.instructions}
            </p>
          </div>
        )}

        <div
          style={{
            border: '2px dashed var(--border-2)',
            borderRadius: 'var(--radius-lg, 12px)',
            padding: '32px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
            cursor: 'pointer',
            transition: 'border-color 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border-2)')}
          onClick={() => onUpload(requirement.id)}
          role="button"
          tabIndex={0}
          onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onUpload(requirement.id); }}
        >
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)', textAlign: 'center' }}>
            Click to select a file or drag and drop
          </p>
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>
            PDF, JPG, PNG up to 20 MB
          </p>
        </div>

        {requirement.template_url && (
          <a
            href={requirement.template_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: '13px', color: 'var(--link)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download blank template
          </a>
        )}
      </aside>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Timeline Tab
// ─────────────────────────────────────────────────────────────────────────────

interface TimelineTabProps {
  requirements: Requirement[];
  onRowClick: (req: Requirement) => void;
}

function TimelineTab({ requirements, onRowClick }: TimelineTabProps) {
  const grouped = groupByCategory(requirements);

  if (requirements.length === 0) {
    return (
      <EmptyState
        icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
        title="No requirements found"
        description="Requirements will appear here once the discovery run completes."
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {Array.from(grouped.entries()).map(([category, reqs]) => (
        <section key={category}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d={CATEGORY_ICONS[category]} />
            </svg>
            <h3 style={{ margin: 0, fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {CATEGORY_LABELS[category]}
            </h3>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>({reqs.length})</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {reqs.map(req => (
              <Button unstyled
                key={req.id}
                onClick={() => onRowClick(req)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 16px',
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md, 8px)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  width: '100%',
                  transition: 'border-color 0.15s, background 0.15s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)';
                  (e.currentTarget as HTMLElement).style.background = 'var(--surface-2)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)';
                  (e.currentTarget as HTMLElement).style.background = 'var(--surface)';
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                    <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text)' }}>
                      {req.name}
                    </span>
                    {req.is_mandatory && (
                      <Pill variant="danger" size="sm">Required</Pill>
                    )}
                  </div>
                  {req.description && (
                    <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {req.description}
                    </p>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
                  {req.due_date && (
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      Due <DateFormatter date={req.due_date} format="absolute" />
                    </span>
                  )}
                  <StatusBadge type="doc" status={req.status} size="sm" />
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 18l6-6-6-6" />
                  </svg>
                </div>
              </Button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sources Tab
// ─────────────────────────────────────────────────────────────────────────────

interface SourcesTabProps {
  sources: (DiscoverySource & { requirement_ids: string[] })[];
  requirements: Requirement[];
}

function SourcesTab({ sources, requirements }: SourcesTabProps) {
  const reqById = new Map(requirements.map(r => [r.id, r]));

  if (sources.length === 0) {
    return (
      <EmptyState
        icon="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101"
        title="No sources yet"
        description="Data sources will appear after discovery completes."
      />
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            {['Source', 'Country', 'Description', 'Requirements generated'].map(h => (
              <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sources.map(src => (
            <tr key={src.id} style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={{ padding: '12px', fontWeight: 600, color: 'var(--text)' }}>
                {src.name}
              </td>
              <td style={{ padding: '12px' }}>
                {/* DiscoverySource doesn't have country in base type, render category */}
                <Pill variant="muted" size="sm">{src.category}</Pill>
              </td>
              <td style={{ padding: '12px', color: 'var(--text-secondary)', maxWidth: '300px' }}>
                <p style={{ margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {'description' in src ? (src as DiscoverySource & { description?: string; requirement_ids: string[] }).description ?? '—' : '—'}
                </p>
              </td>
              <td style={{ padding: '12px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {src.requirement_ids.slice(0, 3).map(rid => {
                    const req = reqById.get(rid);
                    return req ? (
                      <Pill key={rid} variant="info" size="sm">{req.name}</Pill>
                    ) : null;
                  })}
                  {src.requirement_ids.length > 3 && (
                    <Pill variant="muted" size="sm">+{src.requirement_ids.length - 3} more</Pill>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function DiscoveryScreen({ discoveryRun, requirements, sources, onUpload }: DiscoveryScreenProps) {
  const [tab, setTab] = useState<'timeline' | 'sources'>('timeline');
  const [selectedReq, setSelectedReq] = useState<Requirement | null>(null);

  const isLoading = !discoveryRun || discoveryRun.status === 'pending' || discoveryRun.status === 'running';

  const tabs = [
    { id: 'timeline', label: 'Timeline', count: requirements.length },
    { id: 'sources', label: 'Sources', count: sources.length },
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '900px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ margin: '0 0 4px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
          Requirements Discovery
        </h1>
        <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-muted)' }}>
          Documents and requirements identified for your relocation corridor.
        </p>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', padding: '64px 24px' }}>
          <LoadingSpinner size={32} />
          <p style={{ margin: 0, fontSize: '15px', color: 'var(--text-secondary)', fontWeight: 500 }}>
            Requirements are being generated…
          </p>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>
            This usually takes less than a minute. The page will refresh automatically.
          </p>
        </div>
      )}

      {/* Content */}
      {!isLoading && (
        <>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: '0', borderBottom: '1px solid var(--border)', marginBottom: '24px' }}>
            {tabs.map(t => (
              <Button unstyled
                key={t.id}
                onClick={() => setTab(t.id as 'timeline' | 'sources')}
                style={{
                  padding: '10px 16px',
                  background: 'none',
                  border: 'none',
                  borderBottom: `2px solid ${tab === t.id ? 'var(--accent)' : 'transparent'}`,
                  color: tab === t.id ? 'var(--accent)' : 'var(--text-muted)',
                  fontSize: '14px',
                  fontWeight: tab === t.id ? 600 : 400,
                  cursor: 'pointer',
                  marginBottom: '-1px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'color 0.15s',
                }}
              >
                {t.label}
                <span style={{
                  minWidth: '20px',
                  height: '20px',
                  borderRadius: '10px',
                  background: tab === t.id ? 'var(--accent)' : 'var(--surface-2)',
                  color: tab === t.id ? '#fff' : 'var(--text-muted)',
                  fontSize: '11px',
                  fontWeight: 700,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0 5px',
                }}>
                  {t.count}
                </span>
              </Button>
            ))}
          </div>

          {tab === 'timeline' && (
            <TimelineTab requirements={requirements} onRowClick={setSelectedReq} />
          )}
          {tab === 'sources' && (
            <SourcesTab sources={sources} requirements={requirements} />
          )}
        </>
      )}

      {/* Upload Panel */}
      <UploadPanel
        requirement={selectedReq}
        onClose={() => setSelectedReq(null)}
        onUpload={(id) => { onUpload(id); setSelectedReq(null); }}
      />
    </div>
  );
}

export default DiscoveryScreen;
