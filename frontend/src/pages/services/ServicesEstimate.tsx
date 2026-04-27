import React, { useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { Link } from 'react-router-dom';
import { PackageSummary } from '../../features/recommendations/PackageSummary';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { parseAssignmentSearchParam, resolveScopedAssignmentId } from '../../utils/employeeAssignmentScope';
import { buildRoute } from '../../navigation/routes';
import { isRfqEnabled } from '../../featureFlags';

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
  const go = (path: string) => navigate({ pathname: path, search: location.search });

  if (!recommendations) {
    return (
      <AppShell title="Estimate review" subtitle="Shortlist vs HR policy caps.">
        <Card padding="lg">
          <p className="text-sm font-medium text-[#0b2b43] mb-1">No estimate yet on this case</p>
          <p className="text-sm text-[#6b7280] mb-4">
            Pick the services you need, answer a few preferences, then choose providers from the
            recommendations to build your shortlist. Your selections save automatically and you
            can come back here any time to see the cost overview vs your HR policy caps.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => go(buildRoute('services'))}>Start with Select services</Button>
            <Button variant="outline" onClick={() => go(buildRoute('servicesRecommendations'))}>
              Open Recommendations
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
      <Card padding="lg" className="mb-6">
        <div className="text-sm text-[#4b5563]">
          Next steps: 1) Select vendors  2) Request quotations  3) Receive offers  4) Decide
        </div>
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
    </AppShell>
  );
};
