import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { EmptyState } from '../components/EmptyState';
import { ContradictionPanel } from '../features/resolution/ContradictionPanel';
import { useCaseContradictionsQuery } from '../hooks/useContradictionsQuery';
import type { Contradiction } from '../features/resolution/types';

/**
 * Resolution surface for one case.
 *
 * Routing contract: the page reads `?case=<caseId>` from the URL.
 * The case list (CasesPage / CaseDetailPage) is the only thing that
 * navigates here — both link to `/resolution?case=<id>`. Visiting
 * `/resolution` bare shows the "pick a case" empty state.
 *
 * Stepping model (Architecture Report §3.8): one contradiction at a
 * time. The user resolves the current one, the parent advances to the
 * next pending one in the list (server order). When the list is empty,
 * we show the "all clear" empty state.
 */
export function ResolutionPage(): JSX.Element {
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('case') ?? '';

  if (!caseId) {
    return (
      <PageShell subtitle="Outstanding exceptions and decisions waiting on you.">
        <EmptyState
          title="Pick a case to start resolving"
          description="The resolution surface works on one case at a time. Open a case from the list, then click 'Resolve contradictions'."
        >
          <Link
            to="/cases"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
          >
            Go to case list
          </Link>
        </EmptyState>
      </PageShell>
    );
  }

  return <ResolutionForCase caseId={caseId} />;
}

interface ResolutionForCaseProps {
  caseId: string;
}

function ResolutionForCase({ caseId }: ResolutionForCaseProps): JSX.Element {
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
  const query = useCaseContradictionsQuery(caseId);

  // Pending = server-side resolution_status is not Resolved AND we haven't
  // optimistically advanced past it in this session. Local resolvedIds is
  // a UX-only nicety so the user doesn't flash the resolved item before
  // the refetch completes.
  const pending = useMemo<Contradiction[]>(() => {
    const list = query.data ?? [];
    return list.filter(
      (c) => c.resolution_status !== 'Resolved' && !resolvedIds.has(c.contradiction_id),
    );
  }, [query.data, resolvedIds]);

  const current = pending[0] ?? null;
  const handleResolved = (contradictionId: string): void => {
    setResolvedIds((prev) => {
      const next = new Set(prev);
      next.add(contradictionId);
      return next;
    });
  };

  const subtitle = current
    ? `${pending.length} contradiction${pending.length === 1 ? '' : 's'} pending on this case.`
    : 'Outstanding exceptions and decisions waiting on you.';

  if (query.isLoading) {
    return (
      <PageShell subtitle={subtitle}>
        <section
          aria-busy="true"
          className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground"
        >
          Loading contradictions for this case…
        </section>
      </PageShell>
    );
  }

  if (query.isError) {
    return (
      <PageShell subtitle={subtitle}>
        <EmptyState
          title="Couldn't load contradictions"
          description={
            query.error instanceof Error
              ? query.error.message
              : 'The contradiction list failed to load. Try again in a moment.'
          }
        >
          <button
            type="button"
            onClick={() => void query.refetch()}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
          >
            Retry
          </button>
        </EmptyState>
      </PageShell>
    );
  }

  if (!current) {
    return (
      <PageShell subtitle="No contradictions outstanding on this case.">
        <EmptyState
          title="All clear"
          description="Every contradiction on this case has been resolved or marked ignored. New contradictions will appear here as agents detect them."
        >
          <Link
            to={`/cases/${caseId}`}
            className="inline-flex items-center justify-center rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            Back to case
          </Link>
        </EmptyState>
      </PageShell>
    );
  }

  return (
    <PageShell subtitle={subtitle}>
      <ContradictionPanel
        key={current.contradiction_id}
        caseId={caseId}
        contradiction={current}
        onResolved={handleResolved}
      />
    </PageShell>
  );
}

interface PageShellProps {
  subtitle: string;
  children: React.ReactNode;
}

function PageShell({ subtitle, children }: PageShellProps): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold text-foreground">Resolution</h1>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </header>
      {children}
    </div>
  );
}
