import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { ProvidersCriteriaWizard } from '../../features/recommendations/ProvidersCriteriaWizard';
import { employeeAPI, servicesAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';

export const ServicesQuestions: React.FC = () => {
  const navigate = useNavigate();
  const { selectedServices, setRecommendations, setShortlist } = useServicesFlow();
  const { assignmentId } = useEmployeeAssignment();
  const [caseId, setCaseId] = useState<string | null>(null);

  const wizardServices = new Set(
    Array.from(selectedServices).filter((k) =>
      ['housing', 'schools', 'movers', 'banks', 'insurances', 'electricity'].includes(k)
    )
  );

  useEffect(() => {
    let cancelled = false;
    if (!assignmentId) return;
    employeeAPI
      .getAssignmentServices(assignmentId)
      .then((res) => {
        if (!cancelled) setCaseId(res.case_id || null);
      })
      .catch(() => {
        if (!cancelled) setCaseId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  if (wizardServices.size === 0) {
    return (
      <AppShell title="Service questions" subtitle="Answer a few questions so we can personalize providers.">
        <Card padding="lg">
          <Alert variant="info">Select at least one service before answering questions.</Alert>
          <Button className="mt-4" onClick={() => navigate('/services')}>
            Back to services
          </Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Service questions" subtitle="Help us refine your provider matches.">
      <ProvidersCriteriaWizard
        selectedServices={wizardServices as unknown as Set<any>}
        onAnswersChange={(_answers, byCategory) => {
          if (!caseId) return;
          const items = Object.entries(byCategory).map(([serviceKey, answers]) => ({
            service_key: serviceKey,
            answers,
          }));
          servicesAPI.saveServiceAnswers(caseId, items).catch(() => {
            // best-effort autosave
          });
        }}
        onComplete={(results) => {
          setRecommendations(results);
          setShortlist(new Map());
          navigate('/services/recommendations');
        }}
        onBack={() => navigate('/services')}
      />
    </AppShell>
  );
};
