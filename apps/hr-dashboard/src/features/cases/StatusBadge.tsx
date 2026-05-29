import { cn } from '../../lib/utils';
import type { CaseStatus } from './types';

/**
 * Visual status chip. Only the statuses we know about get explicit colours;
 * everything else falls back to neutral muted styling so unknown values
 * don't crash the table.
 */
const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-muted text-muted-foreground',
  in_progress: 'bg-primary/10 text-primary',
  on_hold: 'bg-warning/10 text-warning',
  completed: 'bg-success/10 text-success',
  cancelled: 'bg-destructive/10 text-destructive',
};

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  in_progress: 'In progress',
  on_hold: 'On hold',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

export function StatusBadge({ status }: { status: CaseStatus }): JSX.Element {
  const key = String(status);
  const styles = STATUS_STYLES[key] ?? 'bg-muted text-muted-foreground';
  const label =
    STATUS_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        styles,
      )}
    >
      {label}
    </span>
  );
}
