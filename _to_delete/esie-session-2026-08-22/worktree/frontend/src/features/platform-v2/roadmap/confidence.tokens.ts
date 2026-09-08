/**
 * confidence.tokens.ts — P3-04 · Confidence display design tokens
 *
 * Single source of truth for the 4-level confidence treatment shown on every
 * roadmap step card. Colors are CSS-variable-backed (defined in platform.css)
 * so the badge adapts to light/dark theme automatically and stays consistent
 * with the rest of the ReloPass platform-v2 UI — rather than hard-coding hexes.
 *
 * Semantic mapping:
 *   HIGH    → success (green)  — verified against an official source
 *   MEDIUM  → accent  (teal)   — reliable but confirm the details
 *   LOW     → warning (amber)  — unverified, action recommended (consult a lawyer)
 *   UNKNOWN → neutral (grey)   — no source found, human review required
 *
 * Color is never the only signal: each level also has a distinct Lucide icon
 * and a text label, per WCAG.
 */
import { ShieldCheck, Info, AlertTriangle, HelpCircle, type LucideIcon } from 'lucide-react';

export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';

/** Per-step confidence metadata. All optional on the wire — absent = no display. */
export interface StepConfidence {
  level: ConfidenceLevel;
  /** URL of the official source backing this step. */
  sourceUrl?: string | null;
  /** ISO date the source was last fetched/verified. */
  sourceFetchedAt?: string | null;
  /** One-sentence excerpt from the source. */
  sourceExcerpt?: string | null;
}

export interface ConfidenceToken {
  /** Short pill label. */
  label: string;
  icon: LucideIcon;
  /** Pill background — CSS variable. */
  pillBg: string;
  /** Pill foreground (text + icon) — CSS variable. */
  pillText: string;
  /**
   * Left-border accent on the step card — CSS variable, or `null` for no
   * special border (MEDIUM is intentionally neutral so HIGH/LOW/UNKNOWN read
   * as the visually distinct cases).
   */
  cardBorder: string | null;
  /** One-sentence tooltip; also used as the aria-label suffix. */
  tooltip: string;
}

export const CONFIDENCE_TOKENS: Record<ConfidenceLevel, ConfidenceToken> = {
  HIGH: {
    label: 'High',
    icon: ShieldCheck,
    pillBg: 'var(--success-soft)',
    pillText: 'var(--success-text)',
    cardBorder: 'var(--success)',
    tooltip: 'Backed by an official source we verified.',
  },
  MEDIUM: {
    label: 'Medium',
    icon: Info,
    pillBg: 'var(--accent-soft)',
    pillText: 'var(--accent-text)',
    cardBorder: null,
    tooltip: 'Based on a reliable source — confirm the details for your situation.',
  },
  LOW: {
    label: 'Low',
    icon: AlertTriangle,
    pillBg: 'var(--warning-soft)',
    pillText: 'var(--warning-text)',
    cardBorder: 'var(--warning)',
    tooltip: 'We could not fully verify this step — consult an immigration lawyer before relying on it.',
  },
  UNKNOWN: {
    label: 'Unknown',
    icon: HelpCircle,
    pillBg: 'var(--surface-2)',
    pillText: 'var(--text-secondary)',
    cardBorder: 'var(--text-disabled)',
    tooltip: 'We could not find an official source for this step — expert review required.',
  },
};

/**
 * Route for the LOW-confidence "Consult an immigration lawyer" CTA.
 *
 * NOTE for reviewer: there is no dedicated employee-facing advisor *page* route
 * yet — advisors are matched via POST /api/advisors/match and surfaced on the
 * Discovery screen / Roadmap sidebar (see src/api/advisors.ts). `/advisors` is a
 * placeholder; repoint this one constant once the advisor route lands, or pass an
 * `onConsultAdvisor` handler to RoadmapScreen to drive the in-context match flow.
 */
export const IMMIGRATION_ADVISORS_ROUTE = '/advisors';

/**
 * Resolve the effective confidence level for display. A step that claims
 * HIGH/MEDIUM/LOW but has no backing source is downgraded to UNKNOWN —
 * the system never claims confidence it cannot back.
 */
export function resolveConfidenceLevel(confidence: StepConfidence): ConfidenceLevel {
  if (confidence.level !== 'UNKNOWN' && !confidence.sourceUrl) return 'UNKNOWN';
  return confidence.level;
}
