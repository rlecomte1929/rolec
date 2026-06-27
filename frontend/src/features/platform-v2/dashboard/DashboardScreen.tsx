/**
 * DashboardScreen.tsx — ReloPass HR Dashboard (S1)
 * ─────────────────────────────────────────────────────────────────────────────
 * Route: /dashboard   Visible to: ≥ hr
 *
 * Sections:
 *  1. Attention queue (horizontally scrollable CaseAttentionCards)
 *  2. Active cases snapshot table
 *  3. GlobeCanvas (if globe_canvas_enabled)
 *  4. Recent activity feed (real-time ready)
 *  5. Open exceptions (admin only)
 * ─────────────────────────────────────────────────────────────────────────────
 */

import type * as React from 'react';
import { GlobeCanvas } from '../auth/GlobeCanvas';
import { Button } from '../../../components/antigravity/Button';
import {
  Avatar,
  CountryFlag,
  DateFormatter,
  EmptyState,
  LoadingSpinner,
  Pill,
  ProgressBar,
} from '../shared';
import type { CaseStatus, CaseStage, PlanTier } from '../../../types/relopass-api-contracts';

// ─── Data types ───────────────────────────────────────────────────────────────

export type AttentionIssueType = 'blocked_step' | 'overdue_document' | 'exception_pending';

export interface AttentionCase {
  id: string;
  employee_name: string;
  employee_avatar?: string;
  from_country: string;
  to_country: string;
  stage: CaseStage;
  issue_type: AttentionIssueType;
  issue_description: string;
}

export interface SnapshotCase {
  id: string;
  employee_name: string;
  employee_avatar?: string;
  from_country: string;
  to_country: string;
  stage: CaseStage;
  status: CaseStatus;
  progress_pct: number;
  last_updated: string;
}

export interface ActivityItem {
  id: string;
  actor_name: string;
  actor_avatar?: string;
  action: string;
  case_id: string;
  case_employee: string;
  timestamp: string;
}

export interface PolicyException {
  id: string;
  employee_name: string;
  benefit: string;
  amount?: string;
  justification: string;
  case_id: string;
}

export interface CorridorChip {
  label: string; // e.g. "FR→DE"
  count: number;
}

export interface DashboardScreenProps {
  user_tier: PlanTier;
  attention_cases: AttentionCase[];
  snapshot_cases: SnapshotCase[];
  activity_feed: ActivityItem[];
  open_exceptions: PolicyException[];
  corridor_chips: CorridorChip[];
  globe_canvas_enabled?: boolean;
  loading?: boolean;
  onViewCase: (caseId: string) => void;
  onViewAllCases: () => void;
  onReviewException: (exceptionId: string, caseId: string) => void;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const ISSUE_LABELS: Record<AttentionIssueType, string> = {
  blocked_step: 'Blocked step',
  overdue_document: 'Overdue document',
  exception_pending: 'Exception pending',
};

const ISSUE_VARIANT: Record<AttentionIssueType, 'danger' | 'warning' | 'info'> = {
  blocked_step: 'danger',
  overdue_document: 'warning',
  exception_pending: 'info',
};

const STAGE_LABELS: Record<CaseStage, string> = {
  intake:       'Intake',
  compliance:   'Compliance',
  housing:      'Housing',
  logistics:    'Logistics',
  settling_in:  'Settling in',
  close_out:    'Close-out',
};

// ─── CaseAttentionCard ─────────────────────────────────────────────────────────

function CaseAttentionCard({
  c,
  onView,
}: {
  c: AttentionCase;
  onView: () => void;
}) {
  return (
    <div
      style={{
        flexShrink: 0,
        width: '260px',
        background: 'var(--surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}
    >
      {/* Employee row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Avatar name={c.employee_name} src={c.employee_avatar} size={32} />
        <div style={{ minWidth: 0 }}>
          <p style={{ margin: 0, fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {c.employee_name}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
            <CountryFlag code={c.from_country} />
            <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>→</span>
            <CountryFlag code={c.to_country} />
          </div>
        </div>
        <Pill variant="muted" size="sm" style={{ marginLeft: 'auto', flexShrink: 0 }}>
          {STAGE_LABELS[c.stage] ?? c.stage}
        </Pill>
      </div>

      {/* Issue */}
      <div>
        <Pill variant={ISSUE_VARIANT[c.issue_type]} size="sm">
          {ISSUE_LABELS[c.issue_type]}
        </Pill>
        <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
          {c.issue_description}
        </p>
      </div>

      {/* CTA */}
      <Button unstyled
        onClick={onView}
        style={{
          marginTop: 'auto',
          padding: '7px 12px',
          borderRadius: 'var(--radius-md)',
          background: 'var(--accent-soft)',
          border: '1px solid var(--accent-border)',
          color: 'var(--accent)',
          fontSize: '12px',
          fontWeight: 600,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          justifyContent: 'center',
          transition: 'background var(--transition-fast)',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLElement).style.background = 'var(--accent)';
          (e.currentTarget as HTMLElement).style.color = '#fff';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLElement).style.background = 'var(--accent-soft)';
          (e.currentTarget as HTMLElement).style.color = 'var(--accent)';
        }}
        onFocus={e => {
          (e.currentTarget as HTMLElement).style.background = 'var(--accent)';
          (e.currentTarget as HTMLElement).style.color = '#fff';
        }}
        onBlur={e => {
          (e.currentTarget as HTMLElement).style.background = 'var(--accent-soft)';
          (e.currentTarget as HTMLElement).style.color = 'var(--accent)';
        }}
      >
        View case
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
        </svg>
      </Button>
    </div>
  );
}

// ─── SectionHeader ────────────────────────────────────────────────────────────

function SectionHeader({
  title,
  count,
  action,
}: {
  title: string;
  count?: number;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
      <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
        {title}
      </h2>
      {count !== undefined && (
        <Pill variant={count > 0 ? 'danger' : 'muted'} size="sm">{count}</Pill>
      )}
      {action && (
        <Button unstyled
          onClick={action.onClick}
          style={{
            marginLeft: 'auto',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '13px',
            color: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: 0,
          }}
        >
          {action.label}
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
          </svg>
        </Button>
      )}
    </div>
  );
}

// ─── DashboardScreen ──────────────────────────────────────────────────────────

export function DashboardScreen({
  user_tier,
  attention_cases,
  snapshot_cases,
  activity_feed,
  open_exceptions,
  corridor_chips,
  globe_canvas_enabled = true,
  loading = false,
  onViewCase,
  onViewAllCases,
  onReviewException,
}: DashboardScreenProps) {

  const isAdmin = user_tier === 'admin';

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <LoadingSpinner size={28} centered />
      </div>
    );
  }

  return (
    <div
      style={{
        maxWidth: '960px',
        margin: '0 auto',
        padding: 'var(--spacing-5) var(--spacing-4)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--spacing-8)',
      }}
    >
      {/* ── Section 1: Attention queue ── */}
      <section aria-labelledby="s1-title">
        <SectionHeader
          title="Needs your attention"
          count={attention_cases.length}
        />

        {attention_cases.length === 0 ? (
          <EmptyState
            icon="M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4 12 14.01l-3-3"
            title="Nothing needs your attention right now."
          />
        ) : (
          <div
            style={{
              display: 'flex',
              gap: '12px',
              overflowX: 'auto',
              paddingBottom: 'var(--spacing-2)',
              // Hide scrollbar visually while keeping function
              scrollbarWidth: 'thin',
              scrollbarColor: 'var(--border-subtle) transparent',
            }}
          >
            {attention_cases.map(c => (
              <CaseAttentionCard key={c.id} c={c} onView={() => onViewCase(c.id)} />
            ))}
          </div>
        )}
      </section>

      {/* ── Section 2: Active cases snapshot ── */}
      <section aria-labelledby="s2-title">
        <SectionHeader
          title="Active cases"
          count={snapshot_cases.length}
          action={{ label: 'View all cases →', onClick: onViewAllCases }}
        />

        {snapshot_cases.length === 0 ? (
          <EmptyState
            icon="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"
            title="No active cases."
            description="Cases will appear here once relocation processes are started."
            action={{ label: 'Create a case', onClick: onViewAllCases }}
          />
        ) : (
          <div
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              overflow: 'hidden',
            }}
          >
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '13px',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  {['Employee', 'Corridor', 'Stage', 'Progress', 'Last updated'].map(col => (
                    <th
                      key={col}
                      style={{
                        padding: '10px 16px',
                        textAlign: 'left',
                        fontSize: '12px',
                        fontWeight: 600,
                        color: 'var(--text-tertiary)',
                        background: 'var(--surface-hover)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {snapshot_cases.slice(0, 8).map((c, i) => (
                  <tr
                    key={c.id}
                    onClick={() => onViewCase(c.id)}
                    onKeyDown={(e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onViewCase(c.id); } }}
                    role="button"
                    tabIndex={0}
                    style={{
                      borderBottom: i < snapshot_cases.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                      cursor: 'pointer',
                      transition: 'background var(--transition-fast)',
                    }}
                    onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)'}
                    onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
                  >
                    {/* Employee */}
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Avatar name={c.employee_name} src={c.employee_avatar} size={28} />
                        <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{c.employee_name}</span>
                      </div>
                    </td>
                    {/* Corridor */}
                    <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CountryFlag code={c.from_country} showCode />
                        <span style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>→</span>
                        <CountryFlag code={c.to_country} showCode />
                      </div>
                    </td>
                    {/* Stage */}
                    <td style={{ padding: '12px 16px' }}>
                      <Pill variant="info" size="sm">{STAGE_LABELS[c.stage] ?? c.stage}</Pill>
                    </td>
                    {/* Progress */}
                    <td style={{ padding: '12px 16px', minWidth: '120px' }}>
                      <ProgressBar value={c.progress_pct} />
                    </td>
                    {/* Last updated */}
                    <td style={{ padding: '12px 16px', color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>
                      <DateFormatter date={c.last_updated} format="relative" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Section 3: GlobeCanvas ── */}
      {globe_canvas_enabled && (
        <section aria-labelledby="s3-title">
          <SectionHeader title="Active corridors" />
          <div
            style={{
              background: '#0A0E1A',
              borderRadius: 'var(--radius-lg)',
              overflow: 'hidden',
              height: '320px',
              position: 'relative',
            }}
          >
            <GlobeCanvas style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
          </div>
          {corridor_chips.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '12px' }}>
              {corridor_chips.map(chip => (
                <span
                  key={chip.label}
                  style={{
                    padding: '4px 12px',
                    borderRadius: 'var(--radius-full)',
                    background: 'var(--surface-hover)',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '12px',
                    color: 'var(--text-secondary)',
                    fontWeight: 500,
                  }}
                >
                  {chip.label} · {chip.count} case{chip.count !== 1 ? 's' : ''}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      {/* ── Section 4: Recent activity feed ── */}
      <section aria-labelledby="s4-title">
        <SectionHeader title="Recent activity" />
        {activity_feed.length === 0 ? (
          <EmptyState
            icon="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"
            title="No recent activity."
          />
        ) : (
          <div
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
              overflow: 'hidden',
            }}
          >
            {activity_feed.slice(0, 10).map((item, i) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '12px',
                  padding: '14px 16px',
                  borderBottom: i < activity_feed.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  animation: i === 0 ? 'rp-slide-in 0.25s ease' : undefined,
                }}
              >
                <Avatar name={item.actor_name} src={item.actor_avatar} size={28} style={{ flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.45 }}>
                    <strong>{item.actor_name}</strong> {item.action}{' '}
                    <Button unstyled
                      onClick={() => onViewCase(item.case_id)}
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: 0,
                        cursor: 'pointer',
                        color: 'var(--accent)',
                        fontSize: '13px',
                        fontWeight: 500,
                      }}
                    >
                      {item.case_employee}&apos;s case
                    </Button>
                  </p>
                </div>
                <DateFormatter
                  date={item.timestamp}
                  format="relative"
                  style={{ fontSize: '12px', color: 'var(--text-tertiary)', flexShrink: 0 }}
                />
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Section 5: Open exceptions (admin only) ── */}
      {isAdmin && (
        <section aria-labelledby="s5-title">
          <SectionHeader
            title="Open exceptions"
            count={open_exceptions.length}
          />
          {open_exceptions.length === 0 ? (
            <EmptyState
              icon="M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"
              title="No pending exceptions."
            />
          ) : (
            <div
              style={{
                background: 'var(--surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
              }}
            >
              {open_exceptions.map((ex, i) => (
                <div
                  key={ex.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '16px',
                    padding: '14px 16px',
                    borderBottom: i < open_exceptions.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  }}
                >
                  <Avatar name={ex.employee_name} size={32} style={{ flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ margin: '0 0 2px', fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {ex.employee_name}
                    </p>
                    <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {ex.benefit}{ex.amount ? ` — ${ex.amount}` : ''} ·{' '}
                      <span style={{ color: 'var(--text-tertiary)' }}>{ex.justification.slice(0, 60)}{ex.justification.length > 60 ? '…' : ''}</span>
                    </p>
                  </div>
                  <Button unstyled
                    onClick={() => onReviewException(ex.id, ex.case_id)}
                    style={{
                      flexShrink: 0,
                      padding: '6px 14px',
                      borderRadius: 'var(--radius-md)',
                      background: 'var(--surface-hover)',
                      border: '1px solid var(--border-default)',
                      color: 'var(--text-secondary)',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all var(--transition-fast)',
                    }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLElement).style.background = 'var(--accent-soft)';
                      (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent-border)';
                      (e.currentTarget as HTMLElement).style.color = 'var(--accent)';
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
                      (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-default)';
                      (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
                    }}
                  >
                    Review
                  </Button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <style>{`
        @keyframes rp-slide-in {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

export default DashboardScreen;
