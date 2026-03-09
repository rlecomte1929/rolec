import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { ProvidersCriteriaWizard } from '../../features/recommendations/ProvidersCriteriaWizard';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { logServicesWorkflow } from '../../features/services/servicesWorkflowInstrumentation';
import { useServicesWorkflowState } from '../../features/services/useServicesWorkflowState';
import { employeeAPI, servicesAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { ROUTE_DEFS } from '../../navigation/routes';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';

const SERVICES_QUESTIONS_PATH = ROUTE_DEFS.servicesQuestions.path;

function mergeRecords(
  prev: Record<string, unknown>,
  next: Record<string, unknown>
): Record<string, unknown> {
  return { ...prev, ...next };
}

/** Build initial answers from case (draft + top-level columns) for consistency. */
function caseToInitialAnswers(
  draft: Record<string, unknown> | null,
  caseTopLevel?: { destCity?: string; destCountry?: string; originCity?: string; originCountry?: string }
): Record<string, unknown> {
  const basics = (draft?.relocationBasics || {}) as Record<string, unknown>;
  const destCity = (basics.destCity ?? caseTopLevel?.destCity ?? basics.destCountry ?? caseTopLevel?.destCountry ?? '') as string;
  const destCountry = (basics.destCountry ?? caseTopLevel?.destCountry ?? '') as string;
  const originCity = (basics.originCity ?? caseTopLevel?.originCity ?? basics.originCountry ?? caseTopLevel?.originCountry ?? 'Oslo') as string;
  const cityForCriteria = (destCity || destCountry || '').trim();
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
  const location = useLocation();
  const { selectedServices, setRecommendations, setShortlist, answers, setAnswers } = useServicesFlow();
  const { assignmentId } = useEmployeeAssignment();
  const workflow = useServicesWorkflowState();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [initialAnswers, setInitialAnswers] = useState<Record<string, unknown>>({});
  const [retryTrigger, setRetryTrigger] = useState(0);

  const pathnameRef = useRef(location.pathname);
  pathnameRef.current = location.pathname;
  const mountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    abortControllerRef.current = new AbortController();
    return () => {
      mountedRef.current = false;
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      const path = pathnameRef.current;
      logServicesWorkflow('services_autosave_cancelled_unmount', { pathname: path, reason: 'unmount' });
      if (path !== SERVICES_QUESTIONS_PATH) {
        logServicesWorkflow('services_autosave_cancelled_route_change', { pathname: path, expected: SERVICES_QUESTIONS_PATH });
      }
    };
  }, []);

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
        const updater = (prev: Record<string, unknown>) => mergeRecords(prev, fromCase);
        (setInitialAnswers as React.Dispatch<React.SetStateAction<Record<string, unknown>>>)(updater);
        (setAnswers as React.Dispatch<React.SetStateAction<Record<string, unknown>>>)(updater);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [assignmentId]);

  const lastSavedPayloadRef = useRef<string | null>(null);
  const saveInFlightRef = useRef(false);

  const onAnswersChange = useCallback(
    (newAnswers: Record<string, unknown>, byCategory: Record<string, Record<string, unknown>>) => {
      setAnswers((prev) => mergeRecords(prev, newAnswers));
      if (!caseId) return;
      if (!mountedRef.current) {
        logServicesWorkflow('services_autosave_blocked_wrong_state', {
          pathname: pathnameRef.current,
          reason: 'unmounted',
        });
        return;
      }
      if (pathnameRef.current !== SERVICES_QUESTIONS_PATH) {
        logServicesWorkflow('services_autosave_blocked_wrong_route', {
          pathname: pathnameRef.current,
          expected: SERVICES_QUESTIONS_PATH,
        });
        return;
      }
      if (workflow.isBusy) {
        logServicesWorkflow('services_autosave_blocked_wrong_state', {
          pathname: pathnameRef.current,
          reason: 'workflow_busy',
          state: workflow.state,
        });
        return;
      }
      if (workflow.state !== 'editing' && workflow.state !== 'idle') {
        logServicesWorkflow('services_autosave_blocked_wrong_state', {
          pathname: pathnameRef.current,
          reason: 'workflow_not_editing',
          state: workflow.state,
        });
        return;
      }
      const items = Object.entries(byCategory).map(([serviceKey, ans]) => ({
        service_key: serviceKey,
        answers: ans,
      }));
      const payloadKey = JSON.stringify(items);
      if (lastSavedPayloadRef.current === payloadKey) {
        logServicesWorkflow('services_save_skipped_duplicate', { caseId, pathname: pathnameRef.current });
        return;
      }
      if (saveInFlightRef.current) return;
      lastSavedPayloadRef.current = payloadKey;
      saveInFlightRef.current = true;
      const signal = abortControllerRef.current?.signal;
      logServicesWorkflow('services_save_started', { caseId, pathname: pathnameRef.current, workflowState: workflow.state });
      servicesAPI
        .saveServiceAnswers(caseId, items, signal ? { signal } : undefined)
        .then(() => {
          if (mountedRef.current) {
            logServicesWorkflow('save_preferences_succeeded', { caseId });
          }
        })
        .catch((err: unknown) => {
          const isAbort = err && typeof err === 'object' && ('name' in err || 'code' in err) &&
            ((err as { name?: string }).name === 'AbortError' || (err as { name?: string }).name === 'CanceledError' || (err as { code?: string }).code === 'ERR_CANCELED');
          if (isAbort) {
            logServicesWorkflow('services_save_aborted', { caseId, pathname: pathnameRef.current });
          } else {
            lastSavedPayloadRef.current = null;
            logServicesWorkflow('services_save_failed', { caseId, pathname: pathnameRef.current });
          }
        })
        .finally(() => {
          saveInFlightRef.current = false;
        });
    },
    [caseId, setAnswers, workflow.isBusy, workflow.state]
  );

  const saveAnswersBeforeLoad = useCallback(
    async (ans: Record<string, unknown>, byCategory: Record<string, Record<string, unknown>>) => {
      if (!caseId) throw new Error('Case not ready');
      if (!mountedRef.current || pathnameRef.current !== SERVICES_QUESTIONS_PATH) {
        logServicesWorkflow('services_autosave_blocked_wrong_route', {
          pathname: pathnameRef.current,
          expected: SERVICES_QUESTIONS_PATH,
        });
        return;
      }
      setAnswers((prev) => mergeRecords(prev, ans));
      const items = Object.entries(byCategory).map(([serviceKey, a]) => ({
        service_key: serviceKey,
        answers: a,
      }));
      const payloadKey = JSON.stringify(items);
      if (lastSavedPayloadRef.current === payloadKey) {
        logServicesWorkflow('services_save_skipped_duplicate', { caseId, pathname: pathnameRef.current });
        return;
      }
      workflow.toSavingAnswers();
      const signal = abortControllerRef.current?.signal;
      logServicesWorkflow('services_save_started', { caseId, pathname: pathnameRef.current, workflowState: workflow.state });
      try {
        const res = await servicesAPI.saveServiceAnswers(caseId, items, signal ? { signal } : undefined);
        if (!mountedRef.current) return;
        lastSavedPayloadRef.current = payloadKey;
        const skipped = (res as { skipped_duplicate?: boolean })?.skipped_duplicate;
        if (skipped) {
          logServicesWorkflow('services_save_skipped_duplicate', { caseId });
        } else {
          logServicesWorkflow('save_preferences_succeeded', { caseId });
        }
        workflow.toAnswersSaved();
      } catch (err: unknown) {
        const isAbort = err && typeof err === 'object' && ('name' in err || 'code' in err) &&
          ((err as { name?: string }).name === 'AbortError' || (err as { name?: string }).name === 'CanceledError' || (err as { code?: string }).code === 'ERR_CANCELED');
        if (isAbort) {
          logServicesWorkflow('services_save_aborted', { caseId, pathname: pathnameRef.current });
          return;
        }
        lastSavedPayloadRef.current = null;
        logServicesWorkflow('services_save_failed', { caseId, pathname: pathnameRef.current });
        throw err;
      }
    },
    [caseId, setAnswers, workflow]
  );

  const stableInitialAnswers = useMemo(() => {
    if (Object.keys(initialAnswers).length === 0) return undefined;
    return { ...answers, ...initialAnswers };
  }, [initialAnswers, answers]);

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

  const handleComplete = useCallback(
    (results: Record<string, import('../../features/recommendations/types').RecommendationResponse>) => {
      logServicesWorkflow('recommendations_load_succeeded', {});
      setRecommendations(results);
      setShortlist(new Map());
      workflow.toRecommendationsReady();
      navigate('/services/recommendations');
    },
    [setRecommendations, setShortlist, workflow, navigate]
  );

  const submitLabel =
    workflow.state === 'saving_answers'
      ? 'Saving preferences...'
      : workflow.state === 'loading_recommendations'
        ? 'Loading recommendations...'
        : undefined;

  return (
    <AppShell title="Service questions" subtitle="Help us refine your provider matches.">
      <ServicesNavRibbon />
      {workflow.errorMessage && (
        <Alert variant="error" className="mb-4">
          {workflow.errorMessage}
          <Button
            variant="outline"
            size="sm"
            className="ml-2"
            onClick={() => {
              workflow.clearError();
              setRetryTrigger((c) => c + 1);
            }}
          >
            Retry
          </Button>
        </Alert>
      )}
      <ProvidersCriteriaWizard
        selectedServices={wizardServices as unknown as Set<any>}
        initialAnswers={stableInitialAnswers ?? answers}
        onAnswersChange={onAnswersChange}
        onComplete={handleComplete}
        onBack={() => navigate('/services')}
        autosaveEnabled={!workflow.isBusy}
        saveAnswersBeforeLoad={saveAnswersBeforeLoad}
        isBusy={workflow.isBusy}
        submitLabel={submitLabel}
        onEditingStart={workflow.toEditing}
        onLoadRecommendationsStart={() => {
          logServicesWorkflow('recommendations_load_started', {});
          workflow.toLoadingRecommendations();
        }}
        onError={workflow.toError}
        retryTrigger={retryTrigger}
      />
    </AppShell>
  );
};
