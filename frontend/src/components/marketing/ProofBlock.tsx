import React from 'react';
import { FileSearch, ScanLine, UserCheck } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

/**
 * FRIDAY-004e proof block — the 3 locked EU AI Act credibility lines that sit
 * directly under the hero (source: audit/gtm/proof_block_v1.md §1, layout §5).
 * Three columns on desktop, stacked on mobile. Each item: a small-caps EU AI Act
 * article citation, an icon, and one locked ≤14-word claim line.
 *
 * The "Learn more →" link from the spec (§5) is intentionally omitted: its
 * destination (a dedicated EU AI Act page) does not exist yet and is a tracked
 * FRIDAY-004 follow-up (004c §9). Wire it once that page ships.
 */

const ICONS: Record<string, LucideIcon> = { FileSearch, ScanLine, UserCheck };

export interface ProofItem {
  /** lucide-react icon name (see ICONS map) */
  icon: string;
  /** small-caps EU AI Act article citation shown above the line */
  article: string;
  /** the locked claim line (verbatim) */
  text: string;
}

interface ProofBlockProps {
  /** readonly to accept `as const` content arrays (landingContent) directly */
  items: readonly ProofItem[];
  className?: string;
}

export const ProofBlock: React.FC<ProofBlockProps> = ({ items, className = '' }) => (
  <ul
    className={`grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-10 list-none m-0 p-0 ${className}`}
  >
    {items.map((item) => {
      const Icon = ICONS[item.icon] ?? FileSearch;
      return (
        <li key={item.text} className="flex flex-col gap-3">
          <span
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-marketing-border bg-marketing-surface"
            aria-hidden="true"
          >
            <Icon className="h-5 w-5 text-marketing-accent" strokeWidth={1.75} />
          </span>
          <p className="text-xs font-semibold uppercase tracking-wider text-marketing-accent">
            {item.article}
          </p>
          <p className="text-marketing-body-lg font-semibold text-marketing-primary leading-snug">
            {item.text}
          </p>
        </li>
      );
    })}
  </ul>
);
