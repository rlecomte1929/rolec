/**
 * ConfidenceBadge.tsx — P3-04 · per-step confidence pill
 *
 * Presentational, tokens-driven badge for the 4 confidence levels. Always
 * visible on a roadmap step (no click required) and pairs a color with a
 * distinct icon + text label so color is never the only signal.
 *
 * Accessibility: the badge is a <button> (tabbable by default) that toggles a
 * keyboard-accessible tooltip — Enter/Space toggle, Escape closes, click-outside
 * closes. The tooltip text is also folded into the aria-label so screen-reader
 * users get the full explanation without opening it.
 */
import { useEffect, useId, useRef, useState } from 'react';
import { CONFIDENCE_TOKENS, type ConfidenceLevel } from './confidence.tokens';

export interface ConfidenceBadgeProps {
  level: ConfidenceLevel;
  size?: 'sm' | 'md' | 'lg';
  /** Optional 0–1 score appended to the tooltip + aria-label, e.g. "(0.92)". */
  score?: number | null;
  /** Force the tooltip open — testing convenience. */
  forceTooltipOpen?: boolean;
}

const SIZES = {
  sm: { pad: '1px 6px', font: 11, icon: 12, gap: 3 },
  md: { pad: '2px 8px', font: 12, icon: 14, gap: 4 },
  lg: { pad: '4px 10px', font: 13, icon: 16, gap: 5 },
} as const;

export function ConfidenceBadge({ level, size = 'sm', score, forceTooltipOpen = false }: ConfidenceBadgeProps) {
  const token = CONFIDENCE_TOKENS[level];
  const dims = SIZES[size];
  const Icon = token.icon;
  const [open, setOpen] = useState(false);
  const tooltipId = useId();
  const wrapRef = useRef<HTMLSpanElement>(null);

  const isOpen = open || forceTooltipOpen;
  const scoreSuffix = typeof score === 'number' ? ` (${score.toFixed(2)})` : '';
  const fullText = `${token.tooltip}${scoreSuffix}`;
  const ariaLabel = `Confidence: ${token.label}. ${fullText}`;

  // Close on click outside / Escape.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <span ref={wrapRef} style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-label={ariaLabel}
        aria-describedby={isOpen ? tooltipId : undefined}
        aria-expanded={isOpen}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: `${dims.gap}px`,
          padding: dims.pad,
          borderRadius: '999px',
          border: 'none',
          cursor: 'pointer',
          fontSize: `${dims.font}px`,
          fontWeight: 600,
          lineHeight: 1.4,
          background: token.pillBg,
          color: token.pillText,
        }}
      >
        <Icon size={dims.icon} aria-hidden="true" style={{ flexShrink: 0 }} />
        {token.label}
      </button>

      {isOpen && (
        <span
          id={tooltipId}
          role="tooltip"
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: 0,
            zIndex: 20,
            width: 'max-content',
            maxWidth: '260px',
            padding: '8px 10px',
            borderRadius: 'var(--radius-sm, 6px)',
            background: 'var(--text)',
            color: 'var(--text-inverse)',
            fontSize: '12px',
            fontWeight: 400,
            lineHeight: 1.45,
            boxShadow: 'var(--shadow-md, 0 4px 12px rgba(0,0,0,0.15))',
          }}
        >
          {fullText}
        </span>
      )}
    </span>
  );
}

export default ConfidenceBadge;
