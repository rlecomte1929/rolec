import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card, LoadingButton } from '../../components/antigravity';
import { PackageSummary } from '../../features/recommendations/PackageSummary';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { buildRoute } from '../../navigation/routes';

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
  const { recommendations, shortlist } = useServicesFlow();
  const [rfqNavLoading, setRfqNavLoading] = useState(false);
  const go = (path: string) => navigate({ pathname: path, search: location.search });

  if (!recommendations) {
    return (
      <AppShell title="Estimate" subtitle="Review your shortlisted providers.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">No recommendations yet.</p>
          <Button onClick={() => go(buildRoute('servicesQuestions'))}>Answer questions</Button>
        </Card>
      </AppShell>
    );
  }

  const hasShortlist = shortlist.size > 0;

  return (
    <AppShell title="Estimate review" subtitle="Compare your shortlist with your company's HR policy caps.">
      <ServicesNavRibbon />
      <Card padding="lg" className="mb-6">
        <div className="text-sm text-[#4b5563]">
          Next steps: 1) Select vendors  2) Request quotations  3) Receive offers  4) Decide
        </div>
      </Card>
      <PackageSummary
        results={recommendations}
        selectedPackage={shortlist}
        categoryLabels={CATEGORY_LABELS}
        onBack={() => go(buildRoute('servicesRecommendations'))}
        onStartOver={() => go(buildRoute('services'))}
      />
      <div className="mt-6 flex items-center justify-end">
        <LoadingButton
          loading={rfqNavLoading}
          loadingLabel="Opening next step…"
          disabled={!hasShortlist}
          onClick={async () => {
            setRfqNavLoading(true);
            await new Promise((r) => setTimeout(r, 120));
            go(buildRoute('servicesRfqNew'));
          }}
        >
          Request quotations
        </LoadingButton>
      </div>
    </AppShell>
  );
};
