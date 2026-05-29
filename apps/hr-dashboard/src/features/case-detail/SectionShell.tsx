import { ReactNode } from 'react';
import { EmptyState } from '../../components/EmptyState';

interface SectionShellProps {
  title: string;
  subtitle?: string;
  isLoading?: boolean;
  isError?: boolean;
  error?: unknown;
  onRetry?: () => void;
  /** Shown when not loading + not errored. */
  children: ReactNode;
  /**
   * Optional empty-state message rendered in place of children when
   * `isEmpty` is true (sections vary in what "empty" means).
   */
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
}

/**
 * Standard wrapper for each case-detail section.
 *
 * Centralises the loading + error + empty rendering so every section
 * looks the same. Section components keep their own data-shape rendering
 * concerns and let this component handle the meta-states.
 */
export function SectionShell({
  title,
  subtitle,
  isLoading,
  isError,
  error,
  onRetry,
  children,
  isEmpty,
  emptyTitle,
  emptyDescription,
}: SectionShellProps): JSX.Element {
  return (
    <section aria-labelledby={`section-title-${title}`} className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h2 id={`section-title-${title}`} className="text-xl font-semibold text-foreground">
          {title}
        </h2>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
      </header>

      {isLoading ? (
        <div
          aria-busy="true"
          className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground"
        >
          Loading…
        </div>
      ) : isError ? (
        <EmptyState
          title="Couldn't load this section"
          description={
            error instanceof Error
              ? error.message
              : 'The data for this section failed to load. Try again in a moment.'
          }
        >
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
            >
              Retry
            </button>
          ) : null}
        </EmptyState>
      ) : isEmpty ? (
        <EmptyState
          title={emptyTitle ?? 'Nothing here yet'}
          description={emptyDescription ?? 'No records to show for this section.'}
        />
      ) : (
        children
      )}
    </section>
  );
}
