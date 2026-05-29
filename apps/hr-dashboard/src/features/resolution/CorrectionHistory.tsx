import type { PriorCorrection } from './types';
import { REASON_CODE_LABELS } from './reasonCodes';

interface CorrectionHistoryProps {
  corrections: PriorCorrection[];
  isLoading: boolean;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Compact list of prior corrections on the same canonical entity.
 *
 * Spec from Architecture Report §3.8: the Resolution UI shows the
 * last 5 corrections so the HR reviewer can see whether a pattern is
 * forming on this person / field.
 */
export function CorrectionHistory({
  corrections,
  isLoading,
}: CorrectionHistoryProps): JSX.Element {
  if (isLoading) {
    return (
      <section
        aria-busy="true"
        className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground"
      >
        Loading correction history…
      </section>
    );
  }

  if (corrections.length === 0) {
    return (
      <section className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        No prior corrections on this entity.
      </section>
    );
  }

  return (
    <section
      aria-labelledby="correction-history-title"
      className="rounded-lg border border-border bg-card p-4"
    >
      <h3
        id="correction-history-title"
        className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
      >
        Prior corrections on this entity ({corrections.length})
      </h3>
      <ul className="mt-3 flex flex-col gap-3">
        {corrections.map((c) => (
          <li
            key={c.correction_id}
            className="flex flex-col gap-1 border-t border-border pt-3 first:border-t-0 first:pt-0"
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-medium text-foreground">{c.field}</span>
              <span className="text-xs text-muted-foreground">
                {formatDate(c.corrected_at)}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">
                {REASON_CODE_LABELS[c.reason_code] ?? c.reason_code}
              </span>
              {c.reason_freetext ? ` — ${c.reason_freetext}` : ''}
            </p>
            {c.corrected_by_label ? (
              <p className="text-xs text-muted-foreground">
                by {c.corrected_by_label}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
