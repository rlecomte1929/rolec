import { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description: string;
  /** Optional follow-up content (next-task hint, CTA, etc.). */
  children?: ReactNode;
}

/**
 * Generic empty-state placeholder. Used by every scaffold page until the real
 * UI lands (C1-11b for /cases, C1-11d for the viewer, etc.). Styling pulled
 * entirely from --rp-* tokens via Tailwind utilities.
 */
export function EmptyState({ title, description, children }: EmptyStateProps): JSX.Element {
  return (
    <section
      className="rounded-lg border border-border bg-card px-8 py-12 text-center shadow-sm"
      aria-live="polite"
    >
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      {children ? <div className="mt-6">{children}</div> : null}
    </section>
  );
}
