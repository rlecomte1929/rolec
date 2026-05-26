import React, { useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { Link } from 'react-router-dom';
import { PackageSummary } from '../../features/recommendations/PackageSummary';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { BudgetSummaryTable } from '../../features/services/BudgetSummaryTable';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { parseAssignmentSearchParam, resolveScopedAssignmentId } from '../../utils/employeeAssignmentScope';
import { buildRoute } from '../../navigation/routes';
import { isRfqEnabled } from '../../featureFlags';
import { EmployeeNextActionBar } from '../../components/employee/EmployeeNextActionBar';
import { useTrackLastVisited } from '../../hooks/useTrackLastVisited';

const CATEGORY_LABELS: Record<string, string> = {
  living_areas: 'Living Areas',
  schools: 'Schools',
  movers: 'Movers',
  banks: 'Banks',
  insurance: 'Insurance',
  electricity: 'Electricity',
};

export const ServicesEstimate: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { recommendations, shortlist, displayCurrency, setActiveCaseId } = useServicesFlow();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
  } = useEmployeeAssignment();
  const queryAssignmentId = useMemo(() => parseAssignmentSearchParam(location.search), [location.search]);
  const { effectiveId: assignmentId } = useMemo(
    () => resolveScopedAssignmentId({ linkedSummaries, primaryAssignmentId, queryAssignmentId }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId],
  );
  useEffect(() => {
    setActiveCaseId(assignmentId || null);
    return () => setActiveCaseId(null);
  }, [assignmentId, setActiveCaseId]);
  // Records this as the resume target so re-entering from dashboard
  // returns the user to the estimate / shortlist instead of forcing a
  // restart of the services flow.
  useTrackLastVisited(assignmentId || null);
  const go = (path: string) => navigate({ pathname: path, search: location.search });

  if (!recommendations) {
    return (
      <AppShell title="Estimate review" subtitle="Your services vs your company's policy.">
        {/* AIQ-280: even before service selection, show the policy caps so the
            user knows what their company budgeted for each category. Fixes
            the "No estimate yet" dead-end where the page taught nothing. */}
        {assignmentId && (
          <BudgetSummaryTable
            caseId={assignmentId}
            displayCurrency={displayCurrency}
            className="mb-6"
          />
        )}
        <Card padding="lg">
          {/* Stage 5 (audit): outcome-described empty state per docs/product-copy-rules.md
              ("Empty states: No X yet. [Reason or guidance] → [CTA]") */}
          <p className="text-sm font-medium text-[#0b2b43] mb-1">No estimate yet</p>
          <p className="text-sm text-[#6b7280] mb-4">
            You haven't picked any services yet. Choose what you need, set a few preferences,
            and we'll build a side-by-side view of what your company's policy covers and what
            comes out of pocket. Your selections save automatically — you can come back any time.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => go(buildRoute('services'))}>Start picking services</Button>
            <Button variant="outline" onClick={() => go(buildRoute('servicesRecommendations'))}>
              See recommendations
            </Button>
          </div>
        </Card>
      </AppShell>
    );
  }

  const hasShortlist = shortlist.size > 0;

  return (
    <AppShell title="Estimate review" subtitle="Shortlist vs HR policy caps.">
      <ServicesNavRibbon />
      {/* Stage 5 (audit) — replaced generic numbered list with outcome-described copy
          per audit/re-audit-stage-2-copy.md COPY-5 + docs/product-copy-rules.md
          ("Action button labels: outcome-described, not generic"). */}
      <Card padding="lg" className="mb-6">
        <p className="text-sm text-[#0b2b43] font-medium mb-1">What happens next</p>
        <p className="text-sm text-[#4b5563]">
          Pick the vendors you want quotes from — we'll send the request in one click.
          Offers come back here as vendors respond, then you compare and decide.
        </p>
      </Card>
      <Alert variant="info" className="mb-4">
        <p className="text-sm">
          Estimates and policy comparison below use <strong>{displayCurrency}</strong>. To change currency, go back to{' '}
          <Link to={{ pathname: buildRoute('services'), search: location.search }} className="font-medium underline">
            Select services
          </Link>
          .
        </p>
      </Alert>
      {/* AIQ-280: policy caps overview at the top — independent of shortlist
          state. PackageSummary below this still renders the per-shortlist-item
          cap comparison; this table answers the "what are my caps?" question
          regardless of whether the user has picked services yet. */}
      {assignmentId && (
        <BudgetSummaryTable
          caseId={assignmentId}
          displayCurrency={displayCurrency}
          className="mb-6"
        />
      )}
      <PackageSummary
        results={recommendations}
        selectedPackage={shortlist}
        categoryLabels={CATEGORY_LABELS}
        displayCurrency={displayCurrency}
        onBack={() => go(buildRoute('servicesRecommendations'))}
        onStartOver={() => go(buildRoute('services'))}
      />
      {isRfqEnabled() && (
        <div className="mt-6 flex items-center justify-end">
          <Button disabled={!hasShortlist} onClick={() => go(buildRoute('servicesRfqNew'))}>
            Request quotations
          </Button>
        </div>
      )}

      {/* End-of-services-flow: route to the relocation plan, which is
          the aggregator across all phases. Without this CTA the user
          hits a dead end here and bounces. */}
      {assignmentId && (
        <EmployeeNextActionBar
          status="Estimate ready"
          hint="Your service picks are saved. The relocation plan aggregates all phases — visa, housing, schooling, and more — into one timeline."
          primaryLabel="View my relocation plan →"
          primaryHref={buildRoute('employeeCasePlan', { caseId: assignmentId })}
          secondaryLabel="Back to recommendations"
          secondaryHref={`${buildRoute('servicesRecommendations')}${location.search}`}
        />
      )}
    </AppShell>
  );
};
