import React, { useEffect, useMemo } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { RecommendationResults } from '../../features/recommendations/RecommendationResults';
import { recommendationsEngineAPI } from '../../features/recommendations/api';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { ServicesContextBanner } from '../../features/services/ServicesContextBanner';
import { useServicesMoveBanner } from '../../features/services/useServicesMoveBanner';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { caseIdForAssignment, parseAssignmentSearchParam, resolveScopedAssignmentId } from '../../utils/employeeAssignmentScope';
import { buildRoute, type RouteKey } from '../../navigation/routes';

const CATEGORY_LABELS: Record<string, string> = {
  living_areas: 'Neighbourhoods',
  housing_agencies: 'Housing Agencies',
  schools: 'Schools',
  movers: 'Movers',
  banks: 'Banks',
  insurance: 'Insurance',
  electricity: 'Electricity',
  medical: 'Medical',
  telecom: 'Telecom',
  childcare: 'Childcare',
  storage: 'Storage',
  transport: 'Transport',
  language_integration: 'Language',
  legal_admin: 'Legal & Admin',
  tax_finance: 'Tax & Finance',
  pets: 'Pets',
  partner_career: 'Partner career support',
};

export const ServicesRecommendations: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { recommendations, setRecommendations, shortlist, setShortlist, displayCurrency, setActiveCaseId } = useServicesFlow();
  const { assignmentId: primaryAssignmentId, linkedSummaries } = useEmployeeAssignment();
  // [AIQ-1285] caseId from the path is authoritative; fall back to legacy ?assignment=.
  const { caseId: pathCaseId } = useParams<{ caseId?: string }>();
  const queryAssignmentId = useMemo(
    () => pathCaseId ?? parseAssignmentSearchParam(location.search),
    [pathCaseId, location.search],
  );
  const { effectiveId: assignmentId } = useMemo(
    () => resolveScopedAssignmentId({ linkedSummaries, primaryAssignmentId, queryAssignmentId }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId],
  );
  useEffect(() => {
    // services-state is case-scoped — map assignment_id → case_id (AIQ-1320).
    setActiveCaseId(caseIdForAssignment(linkedSummaries, assignmentId));
    return () => setActiveCaseId(null);
  }, [assignmentId, linkedSummaries, setActiveCaseId]);
  const go = (path: string) => navigate({ pathname: path, search: location.search });
  // AIQ-1334: employee case sub-routes are keyed by case_id — build with the resolved case_id.
  const routeCaseId = caseIdForAssignment(linkedSummaries, assignmentId) ?? pathCaseId ?? '';
  const caseStep = (key: RouteKey) => buildRoute(key, { caseId: routeCaseId });
  // AIQ-1249d: case-context banner — which move this services flow is scoped to.
  const moveBanner = useServicesMoveBanner(assignmentId || null);

  // Δ2/Δ3: when the employee shortlists neighbourhoods, re-rank the housing agencies
  // to favour those serving the shortlisted areas (a boost, never a filter). Debounced;
  // only the housing_agencies block is refreshed, and only once ≥1 neighbourhood is
  // shortlisted. Best-effort — the existing order stays on failure.
  const neighbourhoodShortlistKey = (shortlist.get('living_areas') || []).join(',');
  useEffect(() => {
    const areaIds = shortlist.get('living_areas') || [];
    if (!assignmentId || !recommendations?.housing_agencies || areaIds.length === 0) return;
    const handle = window.setTimeout(() => {
      void (async () => {
        try {
          const { results } = await recommendationsEngineAPI.recommendBatch(assignmentId, ['housing'], areaIds);
          if (results?.housing_agencies) {
            setRecommendations({ ...recommendations, housing_agencies: results.housing_agencies });
          }
        } catch {
          /* best-effort re-rank; keep the current order on failure */
        }
      })();
    }, 600);
    return () => window.clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [neighbourhoodShortlistKey, assignmentId]);

  if (!recommendations || Object.keys(recommendations).length === 0) {
    return (
      <AppShell title="Recommendations" subtitle="Complete service questions first.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">
            Complete the service questions to unlock recommendations.
          </p>
          <Button onClick={() => go(caseStep('caseServicesQuestions'))}>Answer questions</Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Recommendations" subtitle="Shortlist by service.">
      <ServicesContextBanner
        originCity={moveBanner?.originCity}
        destCity={moveBanner?.destCity}
        date={moveBanner?.date}
      />
      <ServicesNavRibbon />
      <Card padding="lg" className="mb-6">
        <div className="text-sm text-[#4b5563]">
          Next steps: 1) Select vendors  2) Request quotations  3) Receive offers  4) Decide
        </div>
      </Card>
      <Alert variant="info" className="mb-4">
        <p className="text-sm">
          Estimates on this page are shown in <strong>{displayCurrency}</strong>. To change currency, go back to{' '}
          <Link to={caseStep('caseServices')} className="font-medium underline">
            Select services
          </Link>
          .
        </p>
      </Alert>
      <RecommendationResults
        results={recommendations}
        categoryLabels={CATEGORY_LABELS}
        selectedPackage={shortlist}
        onSelectedPackageChange={setShortlist}
        onStartOver={() => go(caseStep('caseServices'))}
        onViewSummary={() => go(caseStep('caseServicesEstimate'))}
        displayCurrency={displayCurrency}
        caseId={assignmentId || undefined}
      />
    </AppShell>
  );
};
