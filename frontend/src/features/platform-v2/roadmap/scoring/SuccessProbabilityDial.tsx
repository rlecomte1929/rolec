/**
 * [P2-05b] SuccessProbabilityDial.tsx
 *
 * Visual probability-of-success indicator for the roadmap overview: a radial
 * dial showing the score (rounded to the nearest 5%), colour-coded by band
 * (green ≥80%, amber 60–79%, red <60%), with a MANDATORY, non-removable
 * disclaimer rendered as part of the component.
 *
 * The disclaimer is a required prop AND guarded at runtime — the component
 * refuses to render (throws) if it is missing or blank. This makes it
 * impossible to ship the score without the legal caveat (the task's core
 * trust-safety constraint). No star ratings or gamification language.
 */

import type { ConfidenceBasis } from './successProbability';

export interface SuccessProbabilityDialProps {
  /** Probability of success, 0–100. Re-rounded to nearest 5% defensively. */
  scorePct: number;
  /**
   * MANDATORY disclaimer text, rendered adjacent to the score. Non-removable:
   * the component throws if this is empty or whitespace.
   */
  disclaimer: string;
  /** Whether the estimate is official-rules-only or also uses platform history. */
  confidenceBasis?: ConfidenceBasis;
  /** Optional extra content (e.g. the factors panel) rendered below the disclaimer. */
  children?: React.ReactNode;
}

type Band = 'green' | 'amber' | 'red';

function bandFor(scorePct: number): Band {
  if (scorePct >= 80) return 'green';
  if (scorePct >= 60) return 'amber';
  return 'red';
}

const BAND_COLOR: Record<Band, string> = {
  green: 'var(--success)',
  amber: 'var(--warning)',
  red: 'var(--danger)',
};

const BAND_LABEL: Record<Band, string> = {
  green: 'On track',
  amber: 'Some complexity',
  red: 'High complexity',
};

function roundTo5(pct: number): number {
  const clamped = Math.max(0, Math.min(100, pct));
  return Math.round(clamped / 5) * 5;
}

export function SuccessProbabilityDial({
  scorePct,
  disclaimer,
  confidenceBasis,
  children,
}: SuccessProbabilityDialProps) {
  // Non-removable disclaimer: fail loudly rather than render an unlabelled score.
  if (!disclaimer || !disclaimer.trim()) {
    throw new Error(
      'SuccessProbabilityDial: a non-empty `disclaimer` is required and cannot be removed.',
    );
  }

  const pct = roundTo5(scorePct);
  const band = bandFor(pct);
  const color = BAND_COLOR[band];

  // SVG ring geometry.
  const size = 120;
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = (pct / 100) * circumference;

  return (
    <section
      aria-label="Estimated probability of success"
      style={{
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md, 8px)',
        background: 'var(--surface)',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
        {/* Radial dial */}
        <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
            aria-label={`Estimated success probability ${pct} percent`}>
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke="var(--surface-hover, #e2e8f0)"
              strokeWidth={stroke}
            />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={color}
              strokeWidth={stroke}
              strokeLinecap="round"
              strokeDasharray={`${dash} ${circumference - dash}`}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
            />
          </svg>
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text)', lineHeight: 1 }}>
              {pct}%
            </span>
          </div>
        </div>

        {/* Heading + band */}
        <div style={{ flex: 1, minWidth: '180px' }}>
          <h3 style={{ margin: '0 0 4px', fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>
            Estimated likelihood your case proceeds smoothly
          </h3>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 10px',
              borderRadius: '999px',
              fontSize: '12px',
              fontWeight: 600,
              color,
              background: 'color-mix(in srgb, currentColor 12%, transparent)',
            }}
          >
            <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
            {BAND_LABEL[band]}
          </span>
          {confidenceBasis === 'platform_data' && (
            <p style={{ margin: '8px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
              Adjusted with anonymised outcomes from similar cases.
            </p>
          )}
        </div>
      </div>

      {/* MANDATORY disclaimer — always visible, part of the component, no scroll. */}
      <p
        role="note"
        data-testid="success-probability-disclaimer"
        style={{
          margin: 0,
          padding: '10px 12px',
          fontSize: '12px',
          lineHeight: 1.5,
          color: 'var(--text-secondary, var(--text-muted))',
          background: 'var(--surface-hover, #f1f5f9)',
          borderRadius: 'var(--radius-sm, 6px)',
        }}
      >
        {disclaimer}
      </p>

      {children}
    </section>
  );
}

export default SuccessProbabilityDial;
