import { useMemo } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { CaseDetailNav } from '../features/case-detail/CaseDetailNav';
import { OverviewSection } from '../features/case-detail/OverviewSection';
import { DocumentsSection } from '../features/case-detail/DocumentsSection';
import { StepsSection } from '../features/case-detail/StepsSection';
import { ContradictionsSection } from '../features/case-detail/ContradictionsSection';
import { PolicySection } from '../features/case-detail/PolicySection';
import {
  useCaseOverviewQuery,
  useContradictionsSummaryQuery,
} from '../hooks/useCaseDetailQuery';
import type { SectionKey } from '../features/case-detail/types';

const VALID_SECTIONS: ReadonlySet<SectionKey> = new Set<SectionKey>([
  'overview',
  'documents',
  'steps',
  'contradictions',
  'policy',
]);

function parseSection(raw: string | null): SectionKey {
  if (raw && (VALID_SECTIONS as Set<string>).has(raw)) {
    return raw as SectionKey;
  }
  return 'overview';
}

/**
 * The HR case detail surface (C1-11c).
 *
 * Routing: /cases/:id — the section is held in `?section=<key>` so
 * deep links can target a specific section (e.g. /cases/abc?section=contradictions
 * lands the reviewer directly on the inbox). When no section query
 * param is supplied we default to overview, but never write `overview`
 * back into the URL so the canonical detail URL stays clean.
 *
 * Each section owns its own data fetch via a per-section tanstack-query
 * hook (see hooks/useCaseDetailQuery.ts), so a slow Documents API
 * never blocks the Overview render and a failed Contradictions fetch
 * never breaks the rest of the page.
 */
export function CaseDetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const active = parseSection(searchParams.get('section'));
  const caseId = id ?? '';

  const setActive = (next: SectionKey): void => {
    const params = new URLSearchParams(searchParams);
    if (next === 'overview') {
      params.delete('section');
    } else {
      params.set('section', next);
    }
    setSearchParams(params, { replace: true });
  };

  // Header is driven by the overview query so the case banner reflects
  // the canonical name even before the Documents tab is opened.
  const overview = useCaseOverviewQuery(caseId);
  const contradictions = useContradictionsSummaryQuery(caseId);

  const badges = useMemo(
    () =>
      ({
        contradictions:
          contradictions.data?.pending && contradictions.data.pending > 0
            ? contradictions.data.pending
            : undefined,
      } as Partial<Record<SectionKey, number | undefined>>),
    [contradictions.data?.pending],
  );

  if (!caseId) {
    return <MissingId />;
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <Link
          to="/cases"
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Back to cases
        </Link>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-2xl font-semibold text-foreground">
            {overview.data?.employee.display_name ?? `Case ${caseId.slice(0, 8)}…`}
          </h1>
          <p className="font-mono text-xs text-muted-foreground">{caseId}</p>
        </div>
      </header>

      <div className="flex flex-col gap-6 lg:flex-row">
        <CaseDetailNav active={active} onChange={setActive} badges={badges} />
        <div className="flex-1">
          {active === 'overview' ? <OverviewSection caseId={caseId} /> : null}
          {active === 'documents' ? <DocumentsSection caseId={caseId} /> : null}
          {active === 'steps' ? <StepsSection caseId={caseId} /> : null}
          {active === 'contradictions' ? <ContradictionsSection caseId={caseId} /> : null}
          {active === 'policy' ? <PolicySection /> : null}
        </div>
      </div>
    </div>
  );
}

function MissingId(): JSX.Element {
  return (
    <div className="flex flex-col gap-4">
      <Link to="/cases" className="text-sm font-medium text-primary hover:underline">
        ← Back to cases
      </Link>
      <h1 className="text-xl font-semibold text-destructive">No case id in URL</h1>
      <p className="text-sm text-muted-foreground">
        Open a case from the list — direct links require a valid case id.
      </p>
    </div>
  );
}
