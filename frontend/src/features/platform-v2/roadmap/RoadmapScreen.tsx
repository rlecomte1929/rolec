/**
 * RoadmapScreen.tsx — T07 Roadmap Screen (S3) /roadmap
 * Employee-facing. 4 tracks with steps.
 * Left panel: track list. Right panel: steps for selected track.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { RoadmapTrack, RoadmapStep, StepStatus } from '../../../types/relopass-api-contracts';
import { ProgressBar, StatusBadge, DateFormatter, EmptyState, Pill } from '../shared';
import { ConfidenceBadge } from './ConfidenceBadge';
import {
  CONFIDENCE_TOKENS,
  resolveConfidenceLevel,
  IMMIGRATION_ADVISORS_ROUTE,
  type StepConfidence,
} from './confidence.tokens';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface RoadmapScreenProps {
  tracks: (RoadmapTrack & { steps: RoadmapStep[] })[];
  /** [P1-6] Map of step id → doc chip data. Only steps with doc_count > 0 need entries. */
  docChips?: Record<string, { count: number; worstStatus: string | null }>;
  /** [P1-6] Called when the user clicks a doc chip; receives the step id. */
  onStepDocChipClick?: (stepId: string) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Status icon config
// ─────────────────────────────────────────────────────────────────────────────

type StatusIconConfig = { path: string; color: string };

const STEP_STATUS_ICONS: Record<StepStatus, StatusIconConfig> = {
  pending:           { path: 'M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm0-2a8 8 0 100-16 8 8 0 000 16z', color: 'var(--text-muted)' },
  in_progress:       { path: 'M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83', color: 'var(--accent)' },
  awaiting_employee: { path: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', color: 'var(--warning)' },
  awaiting_vendor:   { path: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', color: 'var(--warning)' },
  awaiting_hr:       { path: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', color: 'var(--warning)' },
  blocked:           { path: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z', color: 'var(--danger)' },
  completed:         { path: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z', color: 'var(--success)' },
  skipped:           { path: 'M13 17h8m0 0l-4-4m4 4l-4 4M3 7h8', color: 'var(--text-disabled)' },
};

function StepStatusIcon({ status }: { status: StepStatus }) {
  const cfg = STEP_STATUS_ICONS[status] ?? STEP_STATUS_ICONS.pending;
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke={cfg.color}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <path d={cfg.path} />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Track List (left panel)
// ─────────────────────────────────────────────────────────────────────────────

interface TrackListProps {
  tracks: (RoadmapTrack & { steps: RoadmapStep[] })[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function TrackList({ tracks, selectedId, onSelect }: TrackListProps) {
  return (
    <nav aria-label="Roadmap tracks" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      {tracks.map(track => {
        const completed = track.steps.filter(s => s.status === 'completed').length;
        const total = track.steps.length;
        const isSelected = track.id === selectedId;
        return (
          <button
            key={track.id}
            onClick={() => onSelect(track.id)}
            aria-pressed={isSelected}
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              padding: '12px 14px',
              borderRadius: 'var(--radius-md, 8px)',
              border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
              background: isSelected ? 'var(--accent-soft)' : 'var(--surface)',
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'all 0.15s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '32px', height: '32px',
                borderRadius: 'var(--radius-md, 8px)',
                background: isSelected ? 'var(--accent)' : 'var(--surface-hover)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke={isSelected ? '#fff' : 'var(--text-muted)'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: 0, fontWeight: 600, fontSize: '14px', color: isSelected ? 'var(--accent-text)' : 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {track.name}
                </p>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>
                  {completed}/{total} steps
                </p>
              </div>
            </div>
            <ProgressBar value={track.progress_pct} height={4} color={isSelected ? 'var(--accent)' : 'var(--text-muted)'} />
          </button>
        );
      })}
    </nav>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Step Row
// ─────────────────────────────────────────────────────────────────────────────

interface StepRowProps {
  step: RoadmapStep;
  vendorName?: string;
  /** [P1-6] Doc count + worst status for the chip badge. */
  docChip?: { count: number; worstStatus: string | null };
  onDocChipClick?: () => void;
}

function StepRow({ step, vendorName, docChip, onDocChipClick }: StepRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  const isBlocked = step.status === 'blocked';

  // [P3-04] Confidence display. Renders only when the backend supplies a level.
  const confidence: StepConfidence | null = step.confidence_level
    ? {
        level: step.confidence_level,
        sourceUrl: step.source_url,
        sourceFetchedAt: step.source_fetched_at,
        sourceExcerpt: step.source_excerpt,
      }
    : null;
  const confLevel = confidence ? resolveConfidenceLevel(confidence) : null;
  const confBorder = confLevel ? CONFIDENCE_TOKENS[confLevel].cardBorder : null;

  function handleTitleClick() {
    const event = new CustomEvent('rp:ai-context', { detail: step, bubbles: true });
    document.dispatchEvent(event);
  }

  return (
    <div
      style={{
        padding: '14px 16px',
        borderRadius: 'var(--radius-md, 8px)',
        border: '1px solid var(--border)',
        borderLeft: isBlocked
          ? '3px solid var(--danger)'
          : confBorder
            ? `4px solid ${confBorder}`
            : '1px solid var(--border)',
        background: 'var(--surface)',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
        <StepStatusIcon status={step.status} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={handleTitleClick}
              style={{
                background: 'none', border: 'none', padding: 0,
                fontWeight: 600, fontSize: '14px', color: 'var(--text)',
                cursor: 'pointer', textAlign: 'left',
              }}
              title="Ask AI about this step"
            >
              {step.title}
            </button>
            <StatusBadge type="step" status={step.status} size="sm" />
            {confLevel && <ConfidenceBadge level={confLevel} size="sm" />}
            {docChip && docChip.count > 0 && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onDocChipClick?.(); }}
                title={`${docChip.count} document${docChip.count === 1 ? '' : 's'}`}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '3px',
                  padding: '2px 6px', borderRadius: 'var(--radius-sm, 4px)',
                  border: '1px solid currentColor', background: 'none',
                  fontSize: '11px', fontWeight: 600, cursor: 'pointer',
                  color: docChip.worstStatus === 'blocked' || docChip.worstStatus === 'rejected'
                    ? 'var(--danger)'
                    : docChip.worstStatus === 'pending_doc' || docChip.worstStatus === 'in_progress' || docChip.worstStatus === 'auto_filled'
                      ? 'var(--warning)'
                      : docChip.worstStatus === 'not_started'
                        ? 'var(--text-muted)'
                        : 'var(--success)',
                }}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {docChip.count}
              </button>
            )}
            {vendorName && (
              <Pill variant="info" size="sm">{vendorName}</Pill>
            )}
          </div>

          {step.due_date && (
            <p style={{ margin: '2px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
              Due: <DateFormatter date={step.due_date} format="absolute" />
            </p>
          )}
        </div>

        {step.description && (
          <button
            onClick={() => setExpanded(e => !e)}
            aria-expanded={expanded}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '2px', flexShrink: 0 }}
            aria-label={expanded ? 'Collapse description' : 'Expand description'}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>
        )}
      </div>

      {expanded && step.description && (
        <p style={{ margin: '0 0 0 28px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {step.description}
        </p>
      )}

      {step.ai_suggestion && expanded && (
        <div style={{ marginLeft: '28px', padding: '10px 12px', background: 'var(--accent-soft)', borderRadius: 'var(--radius-sm, 6px)', borderLeft: '3px solid var(--accent)' }}>
          <p style={{ margin: '0 0 2px', fontSize: '11px', fontWeight: 600, color: 'var(--accent-text)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            AI Suggestion
          </p>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--accent-text)', lineHeight: 1.5 }}>
            {step.ai_suggestion}
          </p>
        </div>
      )}

      {/* [P3-04] Source citation (progressive disclosure) + LOW/UNKNOWN treatments. */}
      {confLevel && (
        <div style={{ marginLeft: '28px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {confidence?.sourceUrl && (
            <>
              <button
                type="button"
                onClick={() => setSourceOpen(o => !o)}
                aria-expanded={sourceOpen}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '4px',
                  alignSelf: 'flex-start', background: 'none', border: 'none', padding: 0,
                  fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', cursor: 'pointer',
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: sourceOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
                  <path d="M6 9l6 6 6-6" />
                </svg>
                {sourceOpen ? 'Hide source' : 'Show source'}
              </button>
              {sourceOpen && (
                <div style={{ padding: '8px 10px', background: 'var(--surface-2)', borderRadius: 'var(--radius-sm, 6px)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <a
                    href={confidence.sourceUrl ?? undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={confidence.sourceUrl ?? undefined}
                    style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  >
                    {confidence.sourceUrl.length > 60 ? `${confidence.sourceUrl.slice(0, 60)}…` : confidence.sourceUrl}
                  </a>
                  {confidence.sourceFetchedAt && (
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Verified <DateFormatter date={confidence.sourceFetchedAt} format="absolute" />
                    </span>
                  )}
                  {confidence.sourceExcerpt && (
                    <p style={{ margin: 0, paddingLeft: '8px', borderLeft: '2px solid var(--border-2)', fontSize: '12px', fontStyle: 'italic', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                      “{confidence.sourceExcerpt}”
                    </p>
                  )}
                </div>
              )}
            </>
          )}

          {confLevel === 'LOW' && (
            <div style={{ padding: '8px 10px', background: 'var(--warning-soft)', borderRadius: 'var(--radius-sm, 6px)' }}>
              <Link to={IMMIGRATION_ADVISORS_ROUTE} style={{ fontSize: '12px', fontWeight: 600, color: 'var(--warning-text)' }}>
                Consult an immigration lawyer →
              </Link>
            </div>
          )}

          {confLevel === 'UNKNOWN' && (
            <p
              aria-label="This step requires expert review before you can rely on it."
              style={{ margin: 0, padding: '8px 10px', background: 'var(--surface-2)', borderRadius: 'var(--radius-sm, 6px)', fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)' }}
            >
              Expert review required
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function RoadmapScreen({ tracks, docChips, onStepDocChipClick }: RoadmapScreenProps) {
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(tracks[0]?.id ?? null);
  const selectedTrack = tracks.find(t => t.id === selectedTrackId) ?? null;

  return (
    <div style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ margin: '0 0 4px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
          Your Roadmap
        </h1>
        <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-muted)' }}>
          Track every step of your relocation journey.
        </p>
      </div>

      {tracks.length === 0 ? (
        <EmptyState
          icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
          title="Roadmap not available yet"
          description="Complete the intake wizard to generate your personalised roadmap."
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 3fr', gap: '20px', alignItems: 'start' }}>
          {/* Left: track list */}
          <TrackList tracks={tracks} selectedId={selectedTrackId} onSelect={setSelectedTrackId} />

          {/* Right: steps */}
          <div>
            {selectedTrack ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <div>
                    <h2 style={{ margin: '0 0 2px', fontSize: '17px', fontWeight: 700, color: 'var(--text)' }}>
                      {selectedTrack.name}
                    </h2>
                    <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>
                      {selectedTrack.steps.filter(s => s.status === 'completed').length} of {selectedTrack.steps.length} steps completed
                    </p>
                  </div>
                  <Pill variant={selectedTrack.progress_pct === 100 ? 'success' : 'info'} size="sm">
                    {selectedTrack.progress_pct}% complete
                  </Pill>
                </div>

                <ProgressBar value={selectedTrack.progress_pct} height={6} style={{ marginBottom: '20px' }} />

                {selectedTrack.steps.length === 0 ? (
                  <EmptyState
                    icon="M12 4v16m8-8H4"
                    title="No steps in this track"
                    description="Steps will appear here once they are generated."
                  />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {selectedTrack.steps
                      .slice()
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map(step => (
                        <StepRow
                          key={step.id}
                          step={step}
                          docChip={docChips?.[step.id]}
                          onDocChipClick={() => onStepDocChipClick?.(step.id)}
                        />
                      ))}
                  </div>
                )}
              </>
            ) : (
              <EmptyState
                icon="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5"
                title="Select a track"
                description="Click a track on the left to see its steps."
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default RoadmapScreen;
