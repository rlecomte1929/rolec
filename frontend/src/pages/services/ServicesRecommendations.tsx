import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { RecommendationResults } from '../../features/recommendations/RecommendationResults';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { ServicesContextBanner } from '../../features/services/ServicesContextBanner';
import { useServicesMoveBanner } from '../../features/services/useServicesMoveBanner';
import { useServicesScope } from '../../features/services/useServicesScope';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';

const CATEGORY_LABELS: Record<string, string> = {
  living_areas: 'Living Areas',
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
};

export const ServicesRecommendations: React.FC = () => {
  const navigate = useNavigate();
  const { recommendations, shortlist, setShortlist, displayCurrency, setActiveCaseId } = useServicesFlow();
  const { assignmentId, linkTo } = useServicesScope();
  useEffect(() => {
    setActiveCaseId(assignmentId || null);
    return () => setActiveCaseId(null);
  }, [assignmentId, setActiveCaseId]);
  const moveBanner = useServicesMoveBanner(assignmentId || null);
  const go = (path: string) => navigate(path);

  if (!recommendations || Object.keys(recommendations).length === 0) {
    return (
      <AppShell title="Recommendations" subtitle="Complete service questions first.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">
            Complete the service questions to unlock recommendations.
          </p>
          <Button onClick={() => go(linkTo('questions'))}>Answer questions</Button>
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
          <Link to={linkTo('services')} className="font-medium underline">
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
        onStartOver={() => go(linkTo('services'))}
        onViewSummary={() => go(linkTo('estimate'))}
        displayCurrency={displayCurrency}
        caseId={assignmentId || undefined}
      />
    </AppShell>
  );
};
