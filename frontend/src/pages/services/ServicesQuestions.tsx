import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { ProvidersCriteriaWizard } from '../../features/recommendations/ProvidersCriteriaWizard';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { employeeAPI, servicesAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';

/** Build initial answers from case (draft + top-level columns) for consistency. */
function caseToInitialAnswers(
  draft: Record<string, unknown> | null,
  caseTopLevel?: { destCity?: string; destCountry?: string; originCity?: string; originCountry?: string }
): Record<string, unknown> {
  const basics = (draft?.relocationBasics || {}) as Record<string, unknown>;
  const destCity = (basics.destCity ?? caseTopLevel?.destCity ?? basics.destCountry ?? caseTopLevel?.destCountry ?? '') as string;
  const destCountry = (basics.destCountry ?? caseTopLevel?.destCountry ?? '') as string;
  const originCity = (basics.originCity ?? caseTopLevel?.originCity ?? basics.originCountry ?? caseTopLevel?.originCountry ?? 'Oslo') as string;
  const cityForCriteria = (destCity || destCountry || 'Singapore').trim();
  return {
    dest_city: cityForCriteria,
    school_dest_city: cityForCriteria,
    move_dest: cityForCriteria,
    origin_city: originCity,
    budget_min: 2000,
    budget_max: 5000,
    child_ages: '8',
    curriculum: 'international',
    school_budget: 'medium',
    school_type: 'international',
    move_type: 'international',
    acc_type: 'apartment',
    acc_bedrooms: 2,
    people: 2,
    packing: 'partial',
    bank_lang: 'en',
    bank_fees: 'medium',
    ins_coverage: 'health',
    ins_family: true,
    elec_green: true,
    elec_flex: 'medium',
  };
}

export const ServicesQuestions: React.FC = () => {
  const navigate = useNavigate();
  const { selectedServices, setRecommendations, setShortlist, answers, setAnswers } = useServicesFlow();
  const { assignmentId } = useEmployeeAssignment();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [initialAnswers, setInitialAnswers] = useState<Record<string, unknown>>({});

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

  useEffect(() => {
    let cancelled = false;
    if (!assignmentId) return;
    getCaseDetailsByAssignmentId(assignmentId)
      .then(({ data, error }) => {
        if (cancelled || error || !data?.case) return;
        const caseData = data.case;
        const topLevel = {
          destCity: caseData.destCity,
          destCountry: caseData.destCountry,
          originCity: caseData.originCity,
          originCountry: caseData.originCountry,
        };
        const fromCase = caseToInitialAnswers((caseData.draft as unknown as Record<string, unknown>) || null, topLevel);
        setInitialAnswers((prev: Record<string, unknown>) => ({ ...prev, ...fromCase }));
        setAnswers((prev: Record<string, unknown>) => ({ ...prev, ...fromCase }));
      })
      .catch(() => {});
    return () => { cancelled = true; };
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
      <ServicesNavRibbon />
      <ProvidersCriteriaWizard
        selectedServices={wizardServices as unknown as Set<any>}
        initialAnswers={Object.keys(initialAnswers).length > 0 ? { ...answers, ...initialAnswers } : answers}
        onAnswersChange={(newAnswers, byCategory) => {
          setAnswers((prev) => ({ ...prev, ...newAnswers }));
          if (!caseId) return;
          const items = Object.entries(byCategory).map(([serviceKey, ans]) => ({
            service_key: serviceKey,
            answers: ans,
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
