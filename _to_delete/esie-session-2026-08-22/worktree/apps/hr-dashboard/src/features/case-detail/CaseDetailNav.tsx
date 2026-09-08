import { cn } from '../../lib/utils';
import type { SectionKey } from './types';

interface CaseDetailNavProps {
  active: SectionKey;
  onChange: (next: SectionKey) => void;
  /** Optional badges (e.g. contradictions count) keyed by section. */
  badges?: Partial<Record<SectionKey, string | number | undefined>>;
}

const SECTIONS: Array<{ key: SectionKey; label: string; description: string }> = [
  { key: 'overview', label: 'Overview', description: 'Employee, family, status, dates.' },
  { key: 'documents', label: 'Documents', description: 'Uploaded sources + extraction confidence.' },
  { key: 'steps', label: 'Steps', description: 'Immigration workflow timeline.' },
  { key: 'contradictions', label: 'Contradictions', description: 'Disagreements between sources awaiting resolution.' },
  { key: 'policy', label: 'Policy', description: 'Corridor rules + entitlement gaps.' },
];

/**
 * Vertical rail navigation for the 5 case-detail sections.
 *
 * The brief allows "shadcn Tabs or vertical nav". Vertical nav reads
 * better for surfaces with descriptive secondary text per item and
 * scales to the Cohort-2 sections (Policy, Steps) without horizontal
 * crowding.
 */
export function CaseDetailNav({ active, onChange, badges }: CaseDetailNavProps): JSX.Element {
  return (
    <nav
      aria-label="Case sections"
      className="sticky top-4 flex w-56 flex-col gap-1 self-start rounded-lg border border-border bg-card p-2 shadow-sm"
    >
      {SECTIONS.map((section) => {
        const isActive = active === section.key;
        const badge = badges?.[section.key];
        return (
          <button
            key={section.key}
            type="button"
            aria-current={isActive ? 'page' : undefined}
            onClick={() => onChange(section.key)}
            className={cn(
              'flex flex-col gap-0.5 rounded-md px-3 py-2 text-left text-sm transition-colors',
              'focus-visible:shadow-focus',
              isActive
                ? 'bg-primary/10 text-primary'
                : 'text-foreground hover:bg-muted',
            )}
          >
            <span className="flex items-center justify-between gap-2 font-medium">
              {section.label}
              {badge !== undefined && badge !== 0 && badge !== '' ? (
                <span
                  className={cn(
                    'inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-xs font-semibold tabular-nums',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground',
                  )}
                >
                  {badge}
                </span>
              ) : null}
            </span>
            <span className={cn('text-xs', isActive ? 'text-primary/80' : 'text-muted-foreground')}>
              {section.description}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
