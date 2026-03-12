import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import { DynamicServicesQuestionnaire, validateDynamicAnswers, type DynamicQuestion } from '../../features/services/DynamicServicesQuestionnaire';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { logServicesWorkflow } from '../../features/services/servicesWorkflowInstrumentation';
import { useServicesWorkflowState } from '../../features/services/useServicesWorkflowState';
import { employeeAPI, servicesAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { ROUTE_DEFS } from '../../navigation/routes';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';
import { SERVICE_CONFIG, type ServiceKey } from '../../features/services/serviceConfig';
import { recommendationsEngineAPI } from '../../features/recommendations/api';
import type { RecommendationResponse } from '../../features/recommendations/types';

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
  const [retryTrigger, setRetryTrigger] = useState(0);
  const [questions, setQuestions] = useState<DynamicQuestion[]>([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [questionsError, setQuestionsError] = useState<string | null>(null);
  const [caseContext, setCaseContext] = useState<{ destCity?: string; destCountry?: string } | null>(null);
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
        if (!cancelled) {
          setCaseId(res.case_id || null);
          // Sync selected services from API (e.g. when visiting /questions directly)
          const selected = new Set(
            (res.services || []).filter((r) => r.selected).map((r) => r.service_key as import('../features/services/serviceConfig').ServiceKey)
          );
          if (selected.size > 0) setSelectedServices(selected);
        }
      })
      .catch(() => {
        if (!cancelled) setCaseId(null);
      });
    return () => { cancelled = true; };
  }, [assignmentId, setSelectedServices]);

  useEffect(() => {
    let cancelled = false;
    if (!assignmentId) return;
    getCaseDetailsByAssignmentId(assignmentId)
      .then(({ data, error }) => {
        if (cancelled || error || !data?.case) return;
        const caseData = data.case;
        setCaseContext({ destCity: caseData.destCity, destCountry: caseData.destCountry });
        const topLevel = {
          destCity: caseData.destCity,
          destCountry: caseData.destCountry,
          originCity: caseData.originCity,
          originCountry: caseData.originCountry,
        };
        const fromCase = caseToInitialAnswers((caseData.draft as unknown as Record<string, unknown>) || null, topLevel);
        (setInitialAnswers as React.Dispatch<React.SetStateAction<Record<string, unknown>>>)((prev) => mergeRecords(prev, fromCase));
        (setAnswers as React.Dispatch<React.SetStateAction<Record<string, unknown>>>)((prev) => mergeRecords(prev, fromCase));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [assignmentId, setAnswers]);

  // Load saved service answers on mount
  useEffect(() => {
    let cancelled = false;
    if (!assignmentId) return;
    servicesAPI
      .getServiceAnswers({ assignmentId })
      .then((res) => {
        if (cancelled || !res?.answers?.length) return;
        const merged: Record<string, unknown> = {};
        for (const row of res.answers) {
          const ans = row.answers || {};
          for (const [k, v] of Object.entries(ans)) {
            if (v !== undefined) merged[k] = v;
          }
        }
        if (Object.keys(merged).length > 0) {
          (setInitialAnswers as React.Dispatch<React.SetStateAction<Record<string, unknown>>>)((prev) => mergeRecords(prev, merged));
          (setAnswers as React.Dispatch<React.SetStateAction<Record<string, unknown>>>)((prev) => mergeRecords(prev, merged));
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [assignmentId, setAnswers]);

  // Load dynamic questions from backend (source of truth)
  useEffect(() => {
    let cancelled = false;
    if (!assignmentId) return;
    setQuestionsLoading(true);
    setQuestionsError(null);
    servicesAPI
      .getServiceQuestions(assignmentId)
      .then((res) => {
        if (cancelled) return;
        const qs = (res?.questions || []) as DynamicQuestion[];
        setQuestions(qs);
        const selected = new Set((res?.selected_services || []) as ServiceKey[]);
        if (selected.size > 0) setSelectedServices(selected);
        // Prefill defaults into local draft without overwriting user edits
        setAnswers((prev) => {
          const next = { ...prev };
          for (const q of qs) {
            if (next[q.question_key] === undefined && q.default !== undefined) {
              next[q.question_key] = q.default;
            }
          }
          return next;
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : (err as Error)?.message;
        setQuestionsError(String(msg || 'Failed to load questions'));
      })
      .finally(() => {
        if (!cancelled) setQuestionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId, setAnswers, setSelectedServices]);

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

  const buildCriteriaForService = (serviceKey: ServiceKey, serviceAnswers: Record<string, unknown>): Record<string, unknown> => {
    // Generic mapping from schema: question_key -> criteria_key (if present)
    const qs = byService[serviceKey] || [];
    const criteria: Record<string, unknown> = {};
    for (const q of qs) {
      const v = serviceAnswers[q.question_key];
      if (v === undefined) continue;
      const ck = q.criteria_key || q.question_key;
      criteria[ck] = v;
    }

    // Canonical destination context (fail-fast is handled earlier, but criteria still includes it)
    const destCity = String(initialAnswers.dest_city ?? '').trim();
    if (destCity) criteria.destination_city = destCity;
    const destCountry = String(caseContext?.destCountry ?? '').trim();
    if (destCountry) criteria.destination_country = destCountry;

    // Minimal service-specific shaping for existing recommendation plugins
    if (serviceKey === 'housing') {
      const minB = typeof criteria.budget_min === 'number' ? (criteria.budget_min as number) : 2000;
      const maxB = typeof criteria.budget_max === 'number' ? (criteria.budget_max as number) : 5000;
      criteria.budget_monthly = { min: minB, max: maxB };
      if (typeof criteria.commute_mins === 'number') {
        criteria.commute_work = { max_minutes: criteria.commute_mins, address: criteria.office_address || '', mode: 'transit' };
      }
      delete criteria.budget_min;
      delete criteria.budget_max;
      delete criteria.commute_mins;
    }
    if (serviceKey === 'schools' && typeof criteria.child_ages === 'string') {
      criteria.child_ages = (criteria.child_ages as string)
        .split(',')
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => !Number.isNaN(n));
      if ((criteria.child_ages as number[]).length === 0) criteria.child_ages = [8];
    }
    if (serviceKey === 'banks') {
      const pl = criteria.preferred_languages;
      if (typeof pl === 'string') criteria.preferred_languages = [pl];
      if (!Array.isArray(criteria.preferred_languages)) criteria.preferred_languages = ['en'];
    }
    if (serviceKey === 'movers') {
      criteria.current_accommodation = {
        type: criteria.acc_type || 'apartment',
        bedrooms: typeof criteria.acc_bedrooms === 'number' ? criteria.acc_bedrooms : 2,
        sqm: 80,
      };
      delete criteria.acc_type;
      delete criteria.acc_bedrooms;
    }
    if (serviceKey === 'insurances' && typeof criteria.coverage_types === 'string') {
      criteria.coverage_types = (criteria.coverage_types as string)
        .split(',')
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean);
      if ((criteria.coverage_types as string[]).length === 0) criteria.coverage_types = ['health'];
    }
    return criteria;
  };

  const onExplicitSave = useCallback(async () => {
    if (!caseId) {
      setSaveMessage('Case not ready. Please go back and try again.');
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

  const submitLabel =
    workflow.state === 'saving_answers'
      ? 'Saving preferences...'
      : workflow.state === 'loading_recommendations'
        ? 'Loading recommendations...'
        : undefined;

  const destinationCity = String(initialAnswers.dest_city ?? '').trim();
  const destinationCountry = String(caseContext?.destCountry ?? '').trim();
  const missingDestination = !destinationCity || !destinationCountry;

  const loadRecommendations = async () => {
    if (missingDestination) {
      workflow.toError('Destination city/country is missing. Please complete your case intake before getting recommendations.');
      return;
    }
    if (!isValid) {
      workflow.toError('Please complete all required questions before continuing.');
      return;
    }
    const saved = await onExplicitSave();
    if (!saved) return;

    workflow.toLoadingRecommendations();
    try {
      const results: Record<string, RecommendationResponse> = {};
      for (const serviceKey of selectedServiceKeys) {
        const svc = SERVICE_CONFIG.find((s) => s.key === serviceKey);
        const backendKey = svc?.backendKey;
        if (!backendKey) continue;
        const criteria = buildCriteriaForService(serviceKey, stableInitialAnswers ?? answers);
        const res = await recommendationsEngineAPI.recommend(backendKey, criteria, 10);
        results[backendKey] = res;
      }
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
            onClick={() => {
              workflow.clearError();
              setRetryTrigger((c) => c + 1);
            }}
          >
            Retry
          </Button>
        </Alert>
      )}
      {questionsError && <Alert variant="error" className="mb-4">{questionsError}</Alert>}
      {missingDestination && (
        <Alert variant="error" className="mb-4">
          Destination city/country is missing. Please complete your case intake before continuing.
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
          Some required fields are missing. Please complete them before continuing.
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
