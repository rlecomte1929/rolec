import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../../components/employee/EmployeeScopedAssignmentPicker';
import { Alert, Button, Card } from '../../components/antigravity';
import { DynamicServicesQuestionnaire, validateDynamicAnswers, type DynamicQuestion } from '../../features/services/DynamicServicesQuestionnaire';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { ServicesContextBanner } from '../../features/services/ServicesContextBanner';
import { logServicesWorkflow } from '../../features/services/servicesWorkflowInstrumentation';
import { useServicesWorkflowState } from '../../features/services/useServicesWorkflowState';
import { servicesAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { ROUTE_DEFS, buildRoute, type RouteKey } from '../../navigation/routes';
import type { ServiceKey } from '../../features/services/serviceConfig';
import { recommendationsEngineAPI } from '../../features/recommendations/api';
import { caseIdForAssignment, parseAssignmentSearchParam, resolveScopedAssignmentId } from '../../utils/employeeAssignmentScope';
import { useTrackLastVisited } from '../../hooks/useTrackLastVisited';

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
  const { selectedServices, setSelectedServices, setRecommendations, setShortlist, answers, setAnswers, displayCurrency, setActiveCaseId } = useServicesFlow();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
    isLoading: assignmentLoading,
  } = useEmployeeAssignment();
  // [AIQ-1285] caseId from the path is authoritative; fall back to legacy ?assignment=.
  const { caseId: pathCaseId } = useParams<{ caseId?: string }>();
  const queryAssignmentId = useMemo(
    () => pathCaseId ?? parseAssignmentSearchParam(location.search),
    [pathCaseId, location.search],
  );
  const { effectiveId: assignmentId, needsPicker } = useMemo(
    () =>
      resolveScopedAssignmentId({
        linkedSummaries,
        primaryAssignmentId,
        queryAssignmentId,
      }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId]
  );
  // AIQ-1334: employee case sub-routes are keyed by case_id (not assignment_id),
  // so in-flow nav targets use the resolved case_id for a consistent URL.
  const routeCaseId = caseIdForAssignment(linkedSummaries, assignmentId) ?? pathCaseId ?? '';
  const caseStep = useCallback(
    (key: RouteKey) => buildRoute(key, { caseId: routeCaseId }),
    [routeCaseId],
  );
  const workflow = useServicesWorkflowState();

  // Services lives outside /employee/case/* but is still part of the
  // user's relocation flow — record the route + assignment query so
  // returning from the dashboard lands them right back on this step.
  useTrackLastVisited(assignmentId || null);

  const [caseId, setCaseId] = useState<string | null>(null);
  const [initialAnswers, setInitialAnswers] = useState<Record<string, unknown>>({});
  const [questions, setQuestions] = useState<DynamicQuestion[]>([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [questionsError, setQuestionsError] = useState<string | null>(null);
  const [caseContext, setCaseContext] = useState<{ destCity?: string; destCountry?: string; originCity?: string; originCountry?: string; date?: string | null } | null>(null);
  const [caseDetailsLoaded, setCaseDetailsLoaded] = useState(false);
  const [isSavingAnswers, setIsSavingAnswers] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  const pathnameRef = useRef(location.pathname);
  pathnameRef.current = location.pathname;
  const mountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // services-state is case-scoped — map assignment_id → case_id (AIQ-1320).
    setActiveCaseId(caseIdForAssignment(linkedSummaries, assignmentId));
    return () => setActiveCaseId(null);
  }, [assignmentId, linkedSummaries, setActiveCaseId]);

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
          ['housing', 'schools', 'movers', 'banks', 'insurances', 'electricity', 'pets'].includes(k)
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
    if (!assignmentId || needsPicker) return;
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
        const destCity = (ctx.destCity ?? ctx.destCountry ?? '');
        const destCountry = (ctx.destCountry ?? '');
        setCaseContext({
          destCity: destCity || undefined,
          destCountry: destCountry || undefined,
          originCity: (ctx.originCity) || undefined,
          originCountry: (ctx.originCountry) || undefined,
          date: res.target_start_date || null,
        });

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
        (setInitialAnswers)(() => merged);
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
  }, [assignmentId, needsPicker, setAnswers, setSelectedServices, questionsFallbackKey]);

  const onAnswersChange = useCallback(
    (next: Record<string, unknown>) => {
      setAnswers(next);
    },
    [setAnswers]
  );

  const selectedServiceKeys = useMemo(() => Array.from(wizardServices), [wizardServices]);

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

  if (assignmentLoading) {
    return (
      <AppShell title="Service questions" subtitle="Short answers to refine provider matches.">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0b2b43] mx-auto mb-4" />
          <p className="text-[#6b7280]">Loading assignment…</p>
        </div>
      </AppShell>
    );
  }

  if (needsPicker && linkedSummaries.length > 0) {
    return (
      <AppShell title="Service questions" subtitle="Choose which assignment these questions apply to.">
        <EmployeeScopedAssignmentPicker
          title="Which assignment?"
          subtitle="Pick which assignment these answers apply to."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('servicesQuestions')}
        />
      </AppShell>
    );
  }

  if (wizardServices.size === 0) {
    return (
      <AppShell title="Service questions" subtitle="Short answers to refine provider matches.">
        <Card padding="lg">
          <Alert variant="info">Select at least one service before answering questions.</Alert>
          <Button
            className="mt-4"
            onClick={() =>
              navigate(caseStep('caseServices'))
            }
          >
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

  const destinationCity = ((initialAnswers.dest_city as string | null | undefined) ?? '').trim();
  const destinationCountry = String(caseContext?.destCountry ?? '').trim();
  // [AIQ-1613] Only block when the BOUND case has NO destination at all. Requiring both a
  // city AND a country fired a false "destination missing" dead-end right after intake
  // (F15) — e.g. country-only intake, or the phantom-case binding fixed in AIQ-1612. A
  // city or a country is enough to proceed into Services.
  const missingDestination = caseDetailsLoaded && !destinationCity && !destinationCountry;

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
      navigate(caseStep('caseServicesRecommendations'));
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      workflow.toError(String(msg || 'Failed to load recommendations.'));
    }
  };

  return (
    <AppShell title="Service questions" subtitle="Refine your provider matches.">
      <ServicesContextBanner
        originCity={caseContext?.originCity || caseContext?.originCountry}
        destCity={caseContext?.destCity || caseContext?.destCountry}
        date={caseContext?.date}
      />
      <ServicesNavRibbon />
      {workflow.state === 'loading_recommendations' && (
        <div
          role="status"
          aria-live="polite"
          aria-busy="true"
          className="mb-4 flex items-center gap-3 rounded-lg border border-[#bfdbfe] bg-[#eff6ff] px-4 py-3 text-sm text-[#1e3a5f]"
        >
          <div className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-[#0b2b43] border-t-transparent" />
          <span>
            <strong>Working in the background:</strong> we&apos;re building your recommendations. This usually takes a
            few seconds—please keep this page open.
          </span>
        </div>
      )}
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
          <Button unstyled
            onClick={() => navigate(caseStep('caseServices'))}
            className="text-sm text-[#0b2b43] hover:underline"
          >
            ← Change services
          </Button>
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
        displayCurrency={displayCurrency}
      />

      {!isValid && (
        <Alert variant="error" className="mt-4">
          Complete required fields before continuing.
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-3 mt-6">
        <Button variant="outline" onClick={() => navigate(caseStep('caseServices'))}>
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
