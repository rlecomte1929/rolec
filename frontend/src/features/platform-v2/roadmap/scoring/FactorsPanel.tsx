/**
 * [P2-05c] FactorsPanel.tsx
 *
 * "Factors affecting your score" — an expandable/collapsible panel that lists
 * which roadmap steps raise or lower the probability-of-success estimate, with
 * the signed percentage-point impact for each. Driven entirely by the
 * `factors[]` returned by successProbability() (P2-05a), so it always matches
 * the computed score.
 *
 * Follows the codebase accordion pattern (role=button header, aria-expanded,
 * chevron rotation, Enter/Space keyboard toggle).
 */

import { useId, useState } from 'react';
import type { ScoreFactor } from './successProbability';

export interface FactorsPanelProps {
  factors: ScoreFactor[];
  /** Whether the panel starts expanded. Defaults to collapsed. */
  defaultExpanded?: boolean;
}

const DIRECTION_COLOR: Record<ScoreFactor['direction'], string> = {
  raises: 'var(--success)',
  lowers: 'var(--danger)',
  neutral: 'var(--text-muted)',
};

function formatImpact(impactPct: number): string {
  if (impactPct === 0) return '±0%';
  const sign = impactPct > 0 ? '+' : '−';
  return `${sign}${Math.abs(impactPct)}%`;
}

export function FactorsPanel({ factors, defaultExpanded = false }: FactorsPanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const panelId = useId();
  const headerId = useId();

  function toggle() {
    setExpanded((e) => !e);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggle();
    }
  }

  return (
    <div
      style={{
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md, 8px)',
        background: 'var(--surface)',
        overflow: 'hidden',
      }}
    >
      <div
        id={headerId}
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        aria-controls={panelId}
        onClick={toggle}
        onKeyDown={onKeyDown}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          padding: '12px 14px',
          cursor: 'pointer',
          fontWeight: 600,
          fontSize: '14px',
          color: 'var(--text)',
        }}
      >
        <span>Factors affecting your score</span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0 }}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>

      <div
        id={panelId}
        role="region"
        aria-labelledby={headerId}
        hidden={!expanded}
        style={{ display: expanded ? 'block' : 'none', padding: '0 14px 12px' }}
      >
        {factors.length === 0 ? (
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>
            No scoring factors are available yet.
          </p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {factors.map((factor, i) => (
              <li
                key={factor.stepId ?? `factor-${i}`}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  paddingTop: i === 0 ? 0 : '8px',
                  borderTop: i === 0 ? 'none' : '1px solid var(--border)',
                }}
              >
                <span
                  style={{
                    flexShrink: 0,
                    minWidth: '44px',
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                    fontWeight: 700,
                    fontSize: '13px',
                    color: DIRECTION_COLOR[factor.direction],
                  }}
                >
                  {formatImpact(factor.impactPct)}
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                    {factor.label}
                  </span>
                  <span style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    {factor.detail}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default FactorsPanel;
