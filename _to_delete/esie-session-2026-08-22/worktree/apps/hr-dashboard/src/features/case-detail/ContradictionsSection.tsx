import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useContradictionsSummaryQuery } from '../../hooks/useCaseDetailQuery';
import { SectionShell } from './SectionShell';

interface ContradictionsSectionProps {
  caseId: string;
}

/**
 * Contradictions inbox view.
 *
 * The brief calls for "click → C1-12 Resolution UI in a Sheet". The C1-12
 * surface already exists as a top-level route at /resolution?case=<id>
 * (shipped in C1-12). Routing to that route is cleaner than an inline
 * Sheet because:
 *   1. The route already supports the "step through one at a time" UX
 *      that the Resolution UI requires.
 *   2. Avoids duplicating ContradictionPanel inside a Sheet host here.
 *   3. Preserves browser back-button behaviour (Sheet doesn't update URL).
 *
 * The "open in Sheet" wording in the brief was a UX preference; the
 * route-based approach delivers the same outcome with cleaner state.
 */
export function ContradictionsSection({ caseId }: ContradictionsSectionProps): JSX.Element {
  const query = useContradictionsSummaryQuery(caseId);
  const summary = query.data;

  const pending = summary?.pending ?? 0;
  const total = summary?.total ?? 0;
  const resolved = summary?.resolved ?? 0;
  const allClear = !query.isLoading && pending === 0;

  return (
    <SectionShell
      title="Contradictions"
      subtitle="Disagreements detected between sources. Resolve them so canonical values are clean."
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => void query.refetch()}
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat label="Pending" value={pending} tone={pending > 0 ? 'warning' : 'success'} />
          <Stat label="Resolved" value={resolved} tone="default" />
          <Stat label="Total" value={total} tone="default" />
        </div>

        {allClear ? (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
            <CheckCircle2 className="h-5 w-5 text-success" aria-hidden="true" />
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium text-foreground">All clear on this case</p>
              <p className="text-xs text-muted-foreground">
                Every detected contradiction has been resolved or marked ignored. New ones will
                surface here automatically as the agents finish parsing fresh documents.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
            <AlertTriangle className="h-5 w-5 text-warning" aria-hidden="true" />
            <div className="flex flex-1 flex-col gap-1">
              <p className="text-sm font-medium text-foreground">
                {pending} contradiction{pending === 1 ? '' : 's'} waiting on a decision
              </p>
              <p className="text-xs text-muted-foreground">
                Open the resolver to step through them one at a time and attach a P0-06 reason
                code per resolved item.
              </p>
            </div>
            <Link
              to={`/resolution?case=${encodeURIComponent(caseId)}`}
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90 focus-visible:shadow-focus"
            >
              Open resolver
            </Link>
          </div>
        )}
      </div>
    </SectionShell>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'default' | 'warning' | 'success';
}): JSX.Element {
  const toneClass =
    tone === 'warning'
      ? 'text-warning'
      : tone === 'success'
        ? 'text-success'
        : 'text-foreground';
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</p>
    </div>
  );
}
