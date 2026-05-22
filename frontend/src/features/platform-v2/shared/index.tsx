/**
 * shared/index.tsx — ReloPass Platform Shared Component Library
 * ─────────────────────────────────────────────────────────────────────────────
 * Exports:
 *   Pill / Badge       — 6 token variants
 *   StatCard           — metric tile with delta
 *   FilterChips        — single-select chip bar
 *   ProgressBar        — segmented / linear
 *   Avatar / Initials  — user avatar with fallback
 *   ConfirmDialog      — modal that blocks action until confirmed
 *   EmptyState         — icon + headline + CTA
 *   LoadingSpinner     — sized spinner
 *   CountryFlag        — emoji helper
 *   DateFormatter      — relative + absolute
 *   StatusBadge        — maps DocStatus/StepStatus/FormStatus to pill
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useEffect, useRef, useState } from 'react';
import type { DocStatus, StepStatus, FormStatus } from '../../../types/relopass-api-contracts';

// ─────────────────────────────────────────────────────────────────────────────
// Pill / Badge
// ─────────────────────────────────────────────────────────────────────────────

export type PillVariant =
  | 'default'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'muted';

const PILL_STYLES: Record<PillVariant, { bg: string; text: string; border: string }> = {
  default: { bg: 'var(--pill-default-bg, var(--surface-hover))',    text: 'var(--pill-default-text, var(--text-secondary))',    border: 'var(--pill-default-border, var(--border-subtle))' },
  success: { bg: 'var(--pill-success-bg, rgba(29,191,162,0.12))',   text: 'var(--pill-success-text, #1DBFA2)',                  border: 'var(--pill-success-border, rgba(29,191,162,0.3))' },
  warning: { bg: 'var(--pill-warning-bg, rgba(239,168,39,0.12))',   text: 'var(--pill-warning-text, #EFA827)',                  border: 'var(--pill-warning-border, rgba(239,168,39,0.3))' },
  danger:  { bg: 'var(--pill-danger-bg, rgba(229,62,62,0.12))',     text: 'var(--pill-danger-text, #E53E3E)',                   border: 'var(--pill-danger-border, rgba(229,62,62,0.3))' },
  info:    { bg: 'var(--pill-info-bg, rgba(74,154,232,0.12))',      text: 'var(--pill-info-text, #4A9AE8)',                     border: 'var(--pill-info-border, rgba(74,154,232,0.3))' },
  muted:   { bg: 'var(--pill-muted-bg, var(--surface-hover))',      text: 'var(--pill-muted-text, var(--text-tertiary))',       border: 'var(--pill-muted-border, transparent)' },
};

export interface PillProps {
  variant?: PillVariant;
  size?: 'sm' | 'md';
  children: React.ReactNode;
  /** Optional dot indicator */
  dot?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function Pill({ variant = 'default', size = 'md', children, dot, className, style }: PillProps) {
  const s = PILL_STYLES[variant];
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: size === 'sm' ? '2px 7px' : '3px 9px',
        borderRadius: 'var(--radius-full)',
        fontSize: size === 'sm' ? '11px' : '12px',
        fontWeight: 600,
        lineHeight: 1.4,
        background: s.bg,
        color: s.text,
        border: `1px solid ${s.border}`,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {dot && (
        <span
          aria-hidden="true"
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: s.text,
            flexShrink: 0,
          }}
        />
      )}
      {children}
    </span>
  );
}

/** Alias — identical to Pill but named Badge for semantic clarity */
export const Badge = Pill;

// ─────────────────────────────────────────────────────────────────────────────
// StatCard
// ─────────────────────────────────────────────────────────────────────────────

export interface StatCardProps {
  title: string;
  value: string | number;
  /** e.g. "+12%" or "-3" — positive shown in success color, negative in danger */
  delta?: string;
  /** Lucide icon path string */
  icon?: string;
  /** Accent color for icon background */
  iconColor?: string;
  onClick?: () => void;
}

export function StatCard({ title, value, delta, icon, iconColor = 'var(--accent)', onClick }: StatCardProps) {
  const isPositive = delta ? !delta.startsWith('-') : null;

  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px',
        display: 'flex',
        gap: '16px',
        alignItems: 'flex-start',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'border-color var(--transition-fast)',
      }}
      onMouseEnter={e => { if (onClick) (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent-border)'; }}
      onMouseLeave={e => { if (onClick) (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)'; }}
    >
      {icon && (
        <div
          aria-hidden="true"
          style={{
            width: '40px',
            height: '40px',
            borderRadius: 'var(--radius-md)',
            background: `${iconColor}18`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d={icon} />
          </svg>
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ margin: '0 0 4px', fontSize: '12px', color: 'var(--text-tertiary)', fontWeight: 500 }}>
          {title}
        </p>
        <p style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2 }}>
          {value}
        </p>
        {delta && (
          <p style={{ margin: '4px 0 0', fontSize: '12px', fontWeight: 500, color: isPositive ? 'var(--status-success, #1DBFA2)' : 'var(--danger, #E53E3E)' }}>
            {delta}
          </p>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FilterChips
// ─────────────────────────────────────────────────────────────────────────────

export interface FilterChip {
  id: string;
  label: string;
  count?: number;
}

export interface FilterChipsProps {
  chips: FilterChip[];
  selected: string;
  onSelect: (id: string) => void;
}

export function FilterChips({ chips, selected, onSelect }: FilterChipsProps) {
  return (
    <div
      role="group"
      aria-label="Filter"
      style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}
    >
      {chips.map(chip => {
        const active = chip.id === selected;
        return (
          <button
            key={chip.id}
            onClick={() => onSelect(chip.id)}
            aria-pressed={active}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              padding: '5px 12px',
              borderRadius: 'var(--radius-full)',
              border: `1px solid ${active ? 'var(--accent-border)' : 'var(--border-subtle)'}`,
              background: active ? 'var(--accent-soft)' : 'var(--surface)',
              color: active ? 'var(--accent)' : 'var(--text-secondary)',
              fontSize: '13px',
              fontWeight: active ? 600 : 400,
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
              whiteSpace: 'nowrap',
            }}
          >
            {chip.label}
            {chip.count !== undefined && (
              <span
                style={{
                  minWidth: '18px',
                  height: '18px',
                  borderRadius: 'var(--radius-full)',
                  background: active ? 'var(--accent)' : 'var(--surface-hover)',
                  color: active ? '#fff' : 'var(--text-tertiary)',
                  fontSize: '11px',
                  fontWeight: 700,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0 4px',
                }}
              >
                {chip.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ProgressBar
// ─────────────────────────────────────────────────────────────────────────────

export interface ProgressBarProps {
  /** 0–100 */
  value: number;
  /** Optional label shown on right */
  label?: string;
  color?: string;
  height?: number;
  /** Show percentage text inside bar when true */
  showPercent?: boolean;
  /** Extra styles applied to the outer wrapper div */
  style?: React.CSSProperties;
}

export function ProgressBar({ value, label, color = 'var(--accent)', height = 6, showPercent, style }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div style={style}>
      {label && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{label}</span>
          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>{clamped}%</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        style={{
          width: '100%',
          height,
          borderRadius: height,
          background: 'var(--surface-hover)',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div
          style={{
            width: `${clamped}%`,
            height: '100%',
            background: color,
            borderRadius: height,
            transition: 'width 0.4s ease',
          }}
        />
        {showPercent && (
          <span
            aria-hidden="true"
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '9px',
              fontWeight: 700,
              color: clamped > 50 ? '#fff' : 'var(--text-secondary)',
            }}
          >
            {clamped}%
          </span>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Avatar / Initials
// ─────────────────────────────────────────────────────────────────────────────

export interface AvatarProps {
  name: string;
  src?: string;
  size?: number;
  /** Override background color */
  color?: string;
  style?: React.CSSProperties;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(p => p[0]?.toUpperCase() ?? '')
    .slice(0, 2)
    .join('');
}

/** Deterministic pastel color from name string */
function nameColor(name: string): string {
  const PALETTE = ['#1DBFA2', '#4A9AE8', '#EFA827', '#9B8DE8', '#E87D4A', '#4AE8C8'];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

export function Avatar({ name, src, size = 32, color, style }: AvatarProps) {
  const [imgError, setImgError] = useState(false);
  const bg = color ?? nameColor(name);

  return (
    <span
      aria-label={name}
      title={name}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        borderRadius: '50%',
        background: src && !imgError ? 'none' : `${bg}22`,
        color: bg,
        fontSize: Math.round(size * 0.38),
        fontWeight: 700,
        flexShrink: 0,
        overflow: 'hidden',
        ...style,
      }}
    >
      {src && !imgError ? (
        <img
          src={src}
          alt={name}
          onError={() => setImgError(true)}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : (
        getInitials(name)
      )}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ConfirmDialog
// ─────────────────────────────────────────────────────────────────────────────

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** 'danger' makes confirm button red */
  variant?: 'default' | 'danger';
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) setTimeout(() => confirmRef.current?.focus(), 50);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="rp-confirm-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 'var(--z-modal)' as never,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={onCancel}
        style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(2px)' }}
      />
      {/* Card */}
      <div
        style={{
          position: 'relative',
          background: 'var(--surface)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-xl)',
          padding: '24px',
          maxWidth: '400px',
          width: '90vw',
        }}
      >
        <h2
          id="rp-confirm-title"
          style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}
        >
          {title}
        </h2>
        {description && (
          <p style={{ margin: '0 0 20px', fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {description}
          </p>
        )}
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-default)',
              background: 'var(--surface)',
              color: 'var(--text-secondary)',
              fontSize: '14px',
              cursor: 'pointer',
            }}
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            style={{
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: variant === 'danger' ? 'var(--danger, #E53E3E)' : 'var(--accent)',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// EmptyState
// ─────────────────────────────────────────────────────────────────────────────

export interface EmptyStateProps {
  /** Lucide icon path (d attribute) */
  icon?: string;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        gap: '12px',
        textAlign: 'center',
      }}
    >
      {icon && (
        <div
          aria-hidden="true"
          style={{
            width: '56px',
            height: '56px',
            borderRadius: 'var(--radius-lg)',
            background: 'var(--surface-hover)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '4px',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d={icon} />
          </svg>
        </div>
      )}
      <p style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
        {title}
      </p>
      {description && (
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-tertiary)', maxWidth: '280px', lineHeight: 1.5 }}>
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          style={{
            marginTop: '4px',
            padding: '8px 18px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--accent)',
            color: '#fff',
            fontWeight: 600,
            fontSize: '13px',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// LoadingSpinner
// ─────────────────────────────────────────────────────────────────────────────

export interface LoadingSpinnerProps {
  size?: number;
  color?: string;
  /** If true, center in parent flex container */
  centered?: boolean;
  label?: string;
}

export function LoadingSpinner({ size = 20, color = 'var(--accent)', centered, label = 'Loading…' }: LoadingSpinnerProps) {
  return (
    <span
      role="status"
      aria-label={label}
      style={{
        display: centered ? 'flex' : 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        ...(centered ? { flex: 1, padding: '40px' } : {}),
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
        aria-hidden="true"
        style={{ animation: 'rp-spin 0.8s linear infinite' }}
      >
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </svg>
      <style>{`@keyframes rp-spin { to { transform: rotate(360deg); } }`}</style>
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CountryFlag
// ─────────────────────────────────────────────────────────────────────────────

/** Returns the emoji flag for a 2-letter ISO country code. Falls back to '🌐'. */
export function countryFlag(isoCode: string): string {
  const code = isoCode.toUpperCase().slice(0, 2);
  if (!/^[A-Z]{2}$/.test(code)) return '🌐';
  return String.fromCodePoint(
    code.charCodeAt(0) - 65 + 0x1F1E6,
    code.charCodeAt(1) - 65 + 0x1F1E6,
  );
}

export interface CountryFlagProps {
  /** ISO 3166-1 alpha-2 country code */
  code: string;
  /** Append the country code as text */
  showCode?: boolean;
  style?: React.CSSProperties;
}

export function CountryFlag({ code, showCode, style }: CountryFlagProps) {
  return (
    <span aria-label={code} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', ...style }}>
      <span aria-hidden="true">{countryFlag(code)}</span>
      {showCode && <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>{code.toUpperCase()}</span>}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DateFormatter
// ─────────────────────────────────────────────────────────────────────────────

/** Returns relative time string, e.g. "2 hours ago", "in 3 days" */
export function formatRelative(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const diff = (d.getTime() - Date.now()) / 1000; // seconds, positive = future
  const abs = Math.abs(diff);
  const future = diff > 0;

  const units: [number, string][] = [
    [60, 'second'],
    [3600, 'minute'],
    [86400, 'hour'],
    [2592000, 'day'],
    [31536000, 'month'],
    [Infinity, 'year'],
  ];

  let prev = 1;
  for (const [limit, unit] of units) {
    if (abs < limit) {
      const value = Math.round(abs / prev);
      if (value < 1) return 'just now';
      const plural = value !== 1 ? 's' : '';
      return future ? `in ${value} ${unit}${plural}` : `${value} ${unit}${plural} ago`;
    }
    prev = limit;
  }
  return d.toLocaleDateString();
}

/** Returns formatted absolute date string */
export function formatAbsolute(date: Date | string, options?: Intl.DateTimeFormatOptions): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', ...options });
}

export interface DateFormatterProps {
  date: Date | string;
  /** 'relative' shows "2 hours ago"; 'absolute' shows "May 20, 2026" */
  format?: 'relative' | 'absolute';
  /** Show the other format as title tooltip */
  tooltip?: boolean;
  style?: React.CSSProperties;
}

export function DateFormatter({ date, format = 'relative', tooltip = true, style }: DateFormatterProps) {
  const d = typeof date === 'string' ? new Date(date) : date;
  const main    = format === 'relative' ? formatRelative(d) : formatAbsolute(d);
  const altTip  = format === 'relative' ? formatAbsolute(d) : formatRelative(d);

  return (
    <time
      dateTime={d.toISOString()}
      title={tooltip ? altTip : undefined}
      style={{ whiteSpace: 'nowrap', ...style }}
    >
      {main}
    </time>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// StatusBadge — maps domain statuses to Pill variants
// ─────────────────────────────────────────────────────────────────────────────

const DOC_STATUS_MAP: Record<string, { label: string; variant: PillVariant }> = {
  required:     { label: 'Missing',    variant: 'muted' },
  submitted:    { label: 'Submitted',  variant: 'info' },
  under_review: { label: 'In Review',  variant: 'warning' },
  approved:     { label: 'Approved',   variant: 'success' },
  rejected:     { label: 'Rejected',   variant: 'danger' },
  expired:      { label: 'Expired',    variant: 'danger' },
  waived:       { label: 'Waived',     variant: 'muted' },
  // legacy DB values kept for backwards compatibility
  pending:      { label: 'Pending',    variant: 'muted' },
  not_required: { label: 'N/A',        variant: 'muted' },
};

const STEP_STATUS_MAP: Record<StepStatus, { label: string; variant: PillVariant }> = {
  pending:           { label: 'Pending',          variant: 'muted' },
  in_progress:       { label: 'In progress',      variant: 'info' },
  awaiting_employee: { label: 'Awaiting you',     variant: 'warning' },
  awaiting_vendor:   { label: 'Awaiting vendor',  variant: 'warning' },
  awaiting_hr:       { label: 'Awaiting HR',      variant: 'warning' },
  blocked:           { label: 'Blocked',           variant: 'danger' },
  completed:         { label: 'Completed',         variant: 'success' },
  skipped:           { label: 'Skipped',           variant: 'muted' },
};

const FORM_STATUS_MAP: Record<FormStatus, { label: string; variant: PillVariant }> = {
  not_started: { label: 'Not started', variant: 'muted' },
  in_progress: { label: 'In progress', variant: 'info' },
  submitted:   { label: 'Submitted',   variant: 'success' },
  reviewed:    { label: 'Reviewed',    variant: 'success' },
};

export interface StatusBadgeProps {
  type: 'doc' | 'step' | 'form';
  status: DocStatus | StepStatus | FormStatus;
  size?: 'sm' | 'md';
}

export function StatusBadge({ type, status, size = 'sm' }: StatusBadgeProps) {
  let entry: { label: string; variant: PillVariant } | undefined;
  if (type === 'doc')  entry = DOC_STATUS_MAP[status as DocStatus];
  if (type === 'step') entry = STEP_STATUS_MAP[status as StepStatus];
  if (type === 'form') entry = FORM_STATUS_MAP[status as FormStatus];
  if (!entry) return <Pill variant="muted" size={size}>{status}</Pill>;
  return <Pill variant={entry.variant} size={size}>{entry.label}</Pill>;
}
