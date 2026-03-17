import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { DynamicServicesQuestionnaire, validateDynamicAnswers, type DynamicQuestion } from '../../features/services/DynamicServicesQuestionnaire';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { logServicesWorkflow } from '../../features/services/servicesWorkflowInstrumentation';
import { useServicesWorkflowState } from '../../features/services/useServicesWorkflowState';
import { servicesAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { ROUTE_DEFS } from '../../navigation/routes';
import type { ServiceKey } from '../../features/services/serviceConfig';
import { recommendationsEngineAPI } from '../../features/recommendations/api';

const SERVICES_QUESTIONS_PATH = ROUTE_DEFS.servicesQuestions.path;

/** Build initial answers from case context for consistency. */
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
    origin_city: originCity,
  };
}

export const ServicesQuestions: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedServices, setSelectedServices, setRecommendations, setShortlist, answers, setAnswers } = useServicesFlow();
  const { assignmentId } = useEmployeeAssignment();
  const workflow = useServicesWorkflowState();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [initialAnswers, setInitialAnswers] = useState<Record<string, unknown>>({});
  const [questions, setQuestions] = useState<DynamicQuestion[]>([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [questionsError, setQuestionsError] = useState<string | null>(null);
  const [caseContext, setCaseContext] = useState<{ destCity?: string; destCountry?: string } | null>(null);
  const [caseDetailsLoaded, setCaseDetailsLoaded] = useState(false);
  const [isSavingAnswers, setIsSavingAnswers] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

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

  const wizardServices = useMemo(
    () =>
      new Set(
        Array.from(selectedServices).filter((k) =>
          ['housing', 'schools', 'movers', 'banks', 'insurances', 'electricity'].includes(k)
        )
      ),
    [selectedServices]
  );

  const questionsFallbackKey = useMemo(
    () => Array.from(wizardServices).sort().join(','),
    [wizardServices]
  );

  // Single combined load: assignment, case, services, answers, questions (replaces 4 separate requests)
  useEffect(() => {
    let cancelled = false;
    if (!assignmentId) return;
    setQuestionsLoading(true);
    setQuestionsError(null);
    const fallback = Array.from(wizardServices);
    servicesAPI
      .getServicesContext(assignmentId, fallback.length ? fallback : undefined)
      .then((res) => {
        if (cancelled) return;
        setCaseId(res.case_id || null);
        const selected = new Set((res.selected_services || []) as ServiceKey[]);
        if (selected.size > 0) setSelectedServices(selected);

        const ctx = res.case_context || {};
        const destCity = (ctx.destCity ?? ctx.destCountry ?? '') as string;
        const destCountry = (ctx.destCountry ?? '') as string;
        setCaseContext({ destCity: destCity || undefined, destCountry: destCountry || undefined });

        const fromCase = caseToInitialAnswers(null, {
          destCity,
          destCountry,
          originCity: ctx.originCity,
          originCountry: ctx.originCountry,
        });
        const merged: Record<string, unknown> = { ...fromCase };
        for (const row of res.answers || []) {
          const ans = row.answers || {};
          for (const [k, v] of Object.entries(ans)) {
            if (v !== undefined) merged[k] = v;
          }
        }
        const qs = (res.questions || []) as DynamicQuestion[];
        const withDefaults = { ...merged };
        for (const q of qs) {
          if (withDefaults[q.question_key] === undefined && q.default !== undefined) {
            withDefaults[q.question_key] = q.default;
          }
        }
        (setInitialAnswers as React.Dispatch<React.SetStateAction<Record<string, unknown>>>)(() => merged);
        (setAnswers as React.Dispatch<React.SetStateAction<Record<string, unknown>>>)(() => withDefaults);
        setQuestions(qs);
        setCaseDetailsLoaded(true);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : (err as Error)?.message;
        setQuestionsError(String(msg || 'Failed to load services context'));
      })
      .finally(() => {
        if (!cancelled) setQuestionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId, setAnswers, setSelectedServices, questionsFallbackKey]);

  const onAnswersChange = useCallback(
    (next: Record<string, unknown>) => {
      setAnswers(next);
    },
    [setAnswers]
  );

  const selectedServiceKeys = useMemo(() => Array.from(wizardServices) as ServiceKey[], [wizardServices]);

  const questionsForSelected = useMemo(() => {
    const selected = new Set(selectedServiceKeys);
    return questions.filter((q) => selected.has(q.service_category as ServiceKey));
  }, [questions, selectedServiceKeys]);

  const byService = useMemo(() => {
    const grouped: Record<string, DynamicQuestion[]> = {};
    for (const q of questionsForSelected) {
      const k = q.service_category;
      if (!grouped[k]) grouped[k] = [];
      grouped[k].push(q);
    }
    return grouped;
  }, [questionsForSelected]);

  const validationErrors = useMemo(() => validateDynamicAnswers(questionsForSelected, answers), [questionsForSelected, answers]);
  const isValid = Object.keys(validationErrors).length === 0;

  const onExplicitSave = useCallback(async () => {
    if (!caseId) {
      setSaveMessage('Case not ready. Go back and try again.');
      return false;
    }
    setIsSavingAnswers(true);
    setSaveMessage('');
    try {
      const items = Object.entries(byService).map(([serviceKey, qs]) => {
        const obj: Record<string, unknown> = {};
        for (const q of qs) obj[q.question_key] = answers[q.question_key];
        return { service_key: serviceKey, answers: obj };
      });
      await servicesAPI.saveServiceAnswers(caseId, items);
      if (mountedRef.current) {
        setSaveMessage('Saved');
        logServicesWorkflow('save_preferences_succeeded', { caseId });
      }
      return true;
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setSaveMessage(String(msg || 'Save failed'));
      logServicesWorkflow('services_save_failed', { caseId });
      return false;
    } finally {
      if (mountedRef.current) setIsSavingAnswers(false);
    }
  }, [answers, byService, caseId]);

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

  const submitLabel =
    workflow.state === 'saving_answers'
      ? 'Saving preferences...'
      : workflow.state === 'loading_recommendations'
        ? 'Loading recommendations...'
        : undefined;

  const destinationCity = String(initialAnswers.dest_city ?? '').trim();
  const destinationCountry = String(caseContext?.destCountry ?? '').trim();
  const missingDestination = caseDetailsLoaded && (!destinationCity || !destinationCountry);

  const loadRecommendations = async () => {
    if (missingDestination) {
      workflow.toError('Destination city/country is missing. Complete case intake before getting recommendations.');
      return;
    }
    if (!isValid) {
      workflow.toError('Complete all required questions before continuing.');
      return;
    }
    if (!assignmentId) {
      workflow.toError('Assignment not available. Go back and try again.');
      return;
    }
    const saved = await onExplicitSave();
    if (!saved) return;

    workflow.toLoadingRecommendations();
    try {
      const { results } = await recommendationsEngineAPI.recommendBatch(
        assignmentId,
        selectedServiceKeys
      );
      setRecommendations(results);
      setShortlist(new Map());
      workflow.toRecommendationsReady();
      navigate('/services/recommendations');
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      workflow.toError(String(msg || 'Failed to load recommendations.'));
    }
  };

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
            onClick={() => workflow.clearError()}
          >
            Retry
          </Button>
        </Alert>
      )}
      {questionsError && <Alert variant="error" className="mb-4">{questionsError}</Alert>}
      {missingDestination && (
        <Alert variant="error" className="mb-4">
          Destination city/country is missing. Complete case intake before continuing.
        </Alert>
      )}
      {saveMessage && (
        <Alert variant={saveMessage === 'Saved' ? 'success' : 'error'} className="mb-4">
          {saveMessage}
        </Alert>
      )}

      <Card padding="lg" className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <button onClick={() => navigate('/services')} className="text-sm text-[#0b2b43] hover:underline">
            ← Change services
          </button>
          {questionsLoading ? (
            <span className="text-sm text-[#6b7280]">Loading questions…</span>
          ) : (
            <span className="text-sm text-[#6b7280]">{questionsForSelected.length} questions</span>
          )}
        </div>
        <h2 className="text-xl font-semibold text-[#0b2b43]">Tell us your preferences</h2>
        <p className="text-sm text-[#6b7280] mt-1">
          We’ll only ask what’s relevant to the services you selected.
        </p>
      </Card>

      <DynamicServicesQuestionnaire
        questions={questionsForSelected}
        answers={answers}
        onChange={onAnswersChange}
      />

      {!isValid && (
        <Alert variant="error" className="mt-4">
          Complete required fields before continuing.
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-3 mt-6">
        <Button variant="outline" onClick={() => navigate('/services')}>
          Back
        </Button>
        <Button variant="outline" onClick={onExplicitSave} disabled={isSavingAnswers || workflow.isBusy}>
          {isSavingAnswers ? 'Saving…' : 'Save'}
        </Button>
        <Button onClick={loadRecommendations} disabled={workflow.isBusy || isSavingAnswers || questionsLoading || missingDestination}>
          {submitLabel ?? 'Get recommendations'}
        </Button>
      </div>
    </AppShell>
  );
};
