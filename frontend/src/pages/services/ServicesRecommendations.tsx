import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card } from '../../components/antigravity';
import { RecommendationResults } from '../../features/recommendations/RecommendationResults';
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
  const { recommendations, shortlist, setShortlist } = useServicesFlow();

  if (!recommendations || Object.keys(recommendations).length === 0) {
    return (
      <AppShell title="Recommendations" subtitle="We need your answers before we can recommend providers.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">
            Complete the service questions to unlock recommendations.
          </p>
          <Button onClick={() => navigate('/services/questions')}>Answer questions</Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Recommendations" subtitle="Shortlist providers for each service.">
      <Card padding="lg" className="mb-6">
        <div className="text-sm text-[#4b5563]">
          Next steps: 1) Select vendors  2) Request quotations  3) Receive offers  4) Decide
        </div>
      </Card>
      <RecommendationResults
        results={recommendations}
        categoryLabels={CATEGORY_LABELS}
        selectedPackage={shortlist}
        onSelectedPackageChange={setShortlist}
        onStartOver={() => navigate('/services')}
        onViewSummary={() => navigate('/services/estimate')}
      />
    </AppShell>
  );
};
