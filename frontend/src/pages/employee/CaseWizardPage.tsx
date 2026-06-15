import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { logger } from '../../lib/logger';
import { PolicyAssistantFab } from '../../features/policy/PolicyAssistantFab';
import { PolicyAssistantDockedShell } from '../../features/policy/PolicyAssistantDockedShell';
import { EmployeePolicyAssistantPanel } from '../../features/policy/EmployeePolicyAssistantPanel';
import { CaseContextBar } from '../../components/case/CaseContextBar';
import { WizardStepRail } from '../../features/employee-journey/WizardStepRail';
import { Card } from '../../components/antigravity';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';
import { patchCase, startResearch } from '../../api/cases';
import { notifyHrEmployeeSaved } from '../../api/notifications';
import { buildNextActionsFromMissingFields, classifyRelocationCase, getRelocationCase } from '../../api/relocation';
import { employeeAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../../utils/demo';
import type { AssignmentStatus, CaseDTO, CaseDraftDTO, NextAction } from '../../types';
import { Step1RelocationBasics } from './wizard/Step1RelocationBasics';
import { Step2EmployeeProfile } from './wizard/Step2EmployeeProfile';
import { Step3FamilyMembers } from './wizard/Step3FamilyMembers';
import { Step4AssignmentContext } from './wizard/Step4AssignmentContext';
import { Step5ReviewCreate } from './wizard/Step5ReviewCreate';
import { useTrackLastVisited } from '../../hooks/useTrackLastVisited';
import { useVariant } from '../../lib/feature-flags';
import type { EmployeeLinkedOverviewRow } from '../../types/employeeAssignmentOverview';

function buildDefaultDraft(): CaseDraftDTO {
  const name = getAuthItem('relopass_name');
  const email = getAuthItem('relopass_email');
  const username = getAuthItem('relopass_username');
  const emailOrUsername = email || (username?.includes('@') ? username : undefined);
  return {
    relocationBasics: {},
    employeeProfile: {
      ...(name && { fullName: name }),
      ...(emailOrUsername && { email: emailOrUsername }),
    },
    familyMembers: {},
    assignmentContext: {},
  };
}

function caseToWizardDraft(caseData: CaseDTO | null, assignment?: { employee_full_name?: string | null } | null): CaseDraftDTO {
  const base = buildDefaultDraft();
  if (!caseData) return base;

  const legacyBasics = {
    originCountry: caseData.originCountry,
    originCity: caseData.originCity,
    destCountry: caseData.destCountry,
    destCity: caseData.destCity,
    purpose: caseData.purpose,
    targetMoveDate: caseData.targetMoveDate,
  };

  const assignmentEmployeeName = assignment?.employee_full_name?.trim() || undefined;
  const baseEmployeeProfile = base.employeeProfile || {};
  const draftEmployeeProfile = caseData.draft?.employeeProfile || {};
  const seededEmployeeProfile = assignmentEmployeeName && !draftEmployeeProfile.fullName
    ? { ...baseEmployeeProfile, fullName: assignmentEmployeeName }
    : baseEmployeeProfile;

  return {
    relocationBasics: {
      ...base.relocationBasics,
      ...legacyBasics,
      ...(caseData.draft?.relocationBasics || {}),
    },
    employeeProfile: {
      ...seededEmployeeProfile,
      ...draftEmployeeProfile,
      // Always fall back to the auth email if the draft has none
      email: draftEmployeeProfile.email || seededEmployeeProfile.email || '',
    },
    familyMembers: {
      ...base.familyMembers,
      ...(caseData.draft?.familyMembers || {}),
    },
    assignmentContext: {
      ...base.assignmentContext,
      ...(caseData.draft?.assignmentContext || {}),
    },
  };
}

/**
 * Variant A — smart pre-fill from assignment context.
 * Only fills fields that are still empty; never overwrites what the employee typed.
 * Returns the enhanced draft plus the set of field keys that were seeded,
 * so the UI can render a "Pre-filled from your profile" chip on those fields.
 */
function buildVariantADraft(
  base: CaseDraftDTO,
  overviewRow: EmployeeLinkedOverviewRow | null,
): { displayDraft: CaseDraftDTO; preFilled: Set<string> } {
  const preFilled = new Set<string>();
  if (!overviewRow?.destination) return { displayDraft: base, preFilled };

  const relBas = { ...base.relocationBasics };
  const empProf = { ...base.employeeProfile };

  const homeCountry = overviewRow.destination.home_country?.trim() || '';
  const hostCountry = overviewRow.destination.host_country?.trim() || '';

  if (!relBas.originCountry && homeCountry) {
    relBas.originCountry = homeCountry;
    preFilled.add('originCountry');
  }

  if (!relBas.destCountry && hostCountry) {
    relBas.destCountry = hostCountry;
    preFilled.add('destCountry');
  }

  // Mirror origin → residenceCountry so the employee doesn't need to re-pick it
  const effectiveOrigin = relBas.originCountry || '';
  if (!empProf.residenceCountry && effectiveOrigin) {
    empProf.residenceCountry = effectiveOrigin;
    preFilled.add('residenceCountry');
  }

  return {
    displayDraft: { ...base, relocationBasics: relBas, employeeProfile: empProf },
    preFilled,
  };
}

const COUNTRY_OPTIONS = [
  { name: 'Germany', cities: ['Berlin', 'Munich'] },
  { name: 'Norway', cities: ['Bergen', 'Oslo'] },
  { name: 'Singapore', cities: ['Singapore'] },
  { name: 'United Kingdom', cities: ['London', 'Manchester'] },
  { name: 'United States', cities: ['New York', 'San Francisco'] },
];

const seedFromString = (value: string) => {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
};

const createRng = (seed: number) => {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 2 ** 32;
  };
};

const formatDate = (date: Date) => date.toISOString().slice(0, 10);

const buildTestDraft = (seedKey: string, baseDraft: CaseDraftDTO, employerNameFallback?: string | null): CaseDraftDTO => {
  const rng = createRng(seedFromString(seedKey));
  const pick = <T,>(items: T[]) => items[Math.floor(rng() * items.length)];

  const originCountry = pick(COUNTRY_OPTIONS);
  const destinationCountry = pick(COUNTRY_OPTIONS.filter((c) => c.name !== originCountry.name));
  const originCity = pick(originCountry.cities);
  const destCity = pick(destinationCountry.cities);
  const purpose = pick(['employment', 'study', 'family', 'other']);
  const daysAhead = Math.floor(rng() * 180) + 1;
  const targetMoveDate = formatDate(new Date(Date.now() + daysAhead * 24 * 60 * 60 * 1000));
  const hasDependents = rng() > 0.5;
  const durationMonths = Math.floor(rng() * 49) + 12;

  const firstNames = ['Alex', 'Sam', 'Jordan', 'Taylor', 'Morgan'];
  const lastNames = ['Lee', 'Patel', 'Ng', 'Garcia', 'Khan'];
  const fullName = `${pick(firstNames)} ${pick(lastNames)}`;
  const spouseName = `${pick(firstNames)} ${pick(lastNames)}`;
  const childName = `${pick(firstNames)} ${pick(lastNames)}`;

  const contractTypes = ['Permanent', 'Fixed-term', 'Secondment', 'Internship'];
  const salaryBands = ['50–100 k€', '100–150 k€', '150–200 k€', '200–300 k€', '300k€+'];

  return {
    relocationBasics: {
      ...baseDraft.relocationBasics,
      originCountry: originCountry.name,
      originCity,
      destCountry: destinationCountry.name,
      destCity,
      purpose,
      targetMoveDate,
      durationMonths,
      hasDependents,
    },
    employeeProfile: {
      ...baseDraft.employeeProfile,
      fullName,
      nationality: originCountry.name,
      passportCountry: originCountry.name,
      passportExpiry: formatDate(new Date(Date.now() + 365 * 24 * 60 * 60 * 1000)),
      residenceCountry: originCountry.name,
      email: `${fullName.replace(/\s+/g, '.').toLowerCase()}@example.com`,
    },
    familyMembers: {
      ...baseDraft.familyMembers,
      maritalStatus: hasDependents ? 'Married' : 'Single',
      spouse: hasDependents ? { fullName: spouseName, relationship: 'Spouse' } : undefined,
      children: hasDependents ? [{ fullName: childName, relationship: 'Child' }] : [],
    },
    assignmentContext: {
      ...baseDraft.assignmentContext,
      employerName: (employerNameFallback && employerNameFallback.trim()) || 'Your employer',
      employerCountry: destinationCountry.name,
      workLocation: destCity,
      contractStartDate: formatDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)),
      contractType: pick(contractTypes),
      salaryBand: pick(salaryBands),
      jobTitle: 'Product Manager',
      seniorityBand: 'Mid',
    },
  };
};

export const CaseWizardPage: React.FC = () => {
  const { caseId: assignmentIdFromRoute, step } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { linkedSummaries } = useEmployeeAssignment();
  const [draft, setDraft] = useState<CaseDraftDTO>(() => buildDefaultDraft());
  const [caseData, setCaseData] = useState<CaseDTO | null>(null);
  const [resolvedCaseId, setResolvedCaseId] = useState<string | null>(null);
  const [requiredFields, setRequiredFields] = useState<string[]>([]);
  const [nextActions, setNextActions] = useState<NextAction[]>([]);
  const [isClassifying, setIsClassifying] = useState(false);
  const [banner, setBanner] = useState('');
  const [error, setError] = useState('');
  const [assignmentStatus, setAssignmentStatus] = useState<AssignmentStatus | null>(null);
  const [hrFeedback, setHrFeedback] = useState<string>('');
  const [hrRequestedSections, setHrRequestedSections] = useState<string[]>([]);
  const [caseFeedback, setCaseFeedback] = useState<Array<{ id: string; message: string; created_at: string }>>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [caseHydrating, setCaseHydrating] = useState(() => Boolean(assignmentIdFromRoute));
  const lastSavedDraftJsonRef = React.useRef<string | null>(null);
  const userEmail = getAuthItem('relopass_email') || getAuthItem('relopass_username') || '';
  const enableTestFill =
    import.meta.env.DEV || userEmail.endsWith('@relopass.com');

  const stepFromRoute = step ? Number(step) : location.pathname.endsWith('/review') ? 5 : 1;
  const currentStep = Math.min(5, Math.max(1, stepFromRoute));

  const stepCompletion = useMemo(() => {
    const b = draft.relocationBasics || {};
    const ep = draft.employeeProfile || {};
    const fm = draft.familyMembers || {};
    const ac = draft.assignmentContext || {};

    const step1Done = Boolean(
      b.originCountry && b.originCity && b.destCountry && b.destCity && b.purpose && b.targetMoveDate
    );
    const step2Done = Boolean(
      ep.fullName && ep.nationality && ep.passportCountry && ep.passportExpiry && ep.residenceCountry && ep.email
    );
    const hasDependents = Boolean(b.hasDependents);
    const spouseOk = Boolean(fm.spouse?.fullName);
    const childOk = Boolean((fm.children || []).some((c) => c.fullName));
    const step3Done = !hasDependents ? Boolean(fm.maritalStatus) : Boolean(fm.maritalStatus && (spouseOk || childOk));
    const step4Done = Boolean(
      ac.employerName && ac.jobTitle && ac.contractStartDate && ac.contractType && ac.salaryBand
    );

    const maxUnlocked =
      step1Done ? (step2Done ? (step3Done ? (step4Done ? 5 : 4) : 3) : 2) : 1;

    const completed: number[] = [];
    if (step1Done) completed.push(1);
    if (step2Done) completed.push(2);
    if (step3Done) completed.push(3);
    if (step4Done) completed.push(4);
    return { step1Done, step2Done, step3Done, step4Done, maxUnlocked, completed };
  }, [draft]);

  const assignmentId = assignmentIdFromRoute;

  // Persist current wizard step as the resume target — re-entering from
  // the dashboard's "Open case" lands the user back on this step instead
  // of forcing a restart from step 1.
  useTrackLastVisited(assignmentId || null);

  // Enforce linear progression: cannot skip ahead.
  useEffect(() => {
    if (!assignmentId) return;
    if (currentStep > stepCompletion.maxUnlocked) {
      setError('Complete the previous steps before continuing.');
      navigate(`/employee/case/${assignmentId}/wizard/${stepCompletion.maxUnlocked}`, { replace: true });
    }
  }, [assignmentId, currentStep, stepCompletion.maxUnlocked, navigate]);

  const loadCase = useCallback(async () => {
    if (!assignmentIdFromRoute) {
      setCaseHydrating(false);
      return;
    }
    setCaseHydrating(true);
    try {
      const { data, error: loadError } = await getCaseDetailsByAssignmentId(assignmentIdFromRoute);
      if (loadError || !data) {
        setCaseData(null);
        setDraft(buildDefaultDraft());
        setResolvedCaseId(null);
        if (loadError) setError(loadError.includes('Case row missing') ? loadError : 'Assignment not found or not visible under RLS.');
      } else {
        setCaseData(data.case);
        setDraft(caseToWizardDraft(data.case, data.assignment));
        setResolvedCaseId(data.case.id);
        lastSavedDraftJsonRef.current = JSON.stringify(
          caseToWizardDraft(data.case, data.assignment)
        );
      }
    } catch {
      setCaseData(null);
      setDraft(buildDefaultDraft());
      setResolvedCaseId(null);
      setError('Assignment not found or not visible under RLS.');
    } finally {
      setCaseHydrating(false);
    }
  }, [assignmentIdFromRoute]);

  const loadRequirements = useCallback(async () => {
    const caseIdForReq = resolvedCaseId || assignmentIdFromRoute;
    if (!caseIdForReq) return;
    try {
      const relocation = await getRelocationCase(caseIdForReq);
      const missing = relocation.missing_fields || [];
      setRequiredFields(missing);
      setNextActions(buildNextActionsFromMissingFields(missing));
    } catch {
      setRequiredFields([]);
      setNextActions([]);
    }
  }, [resolvedCaseId, assignmentIdFromRoute]);

  useEffect(() => {
    void loadCase();
  }, [loadCase]);

  useEffect(() => {
    if (resolvedCaseId) void loadRequirements();
  }, [resolvedCaseId, loadRequirements]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    if (!caseData) return;
    logger.debug('Wizard defaults (relocationBasics):', caseToWizardDraft(caseData).relocationBasics);
  }, [caseData?.id, caseData?.updatedAt]);

  const overviewRowForAssignment = useMemo(
    () => linkedSummaries.find((r) => r.assignment_id === assignmentId) ?? null,
    [linkedSummaries, assignmentId]
  );

  // A/B: onboarding_flow_v2 — variant_a applies smart pre-fill from assignment context
  const onboardingVariant = useVariant('onboarding_flow_v2');
  const { displayDraft, preFilled } = useMemo(
    (): { displayDraft: CaseDraftDTO; preFilled: Set<string> } => {
      if (onboardingVariant !== 'variant_a') {
        return { displayDraft: draft, preFilled: new Set<string>() };
      }
      return buildVariantADraft(draft, overviewRowForAssignment);
    },
    [draft, onboardingVariant, overviewRowForAssignment],
  );

  // Assignment status from canonical overview (avoid extra GET /assignments/current per wizard step).
  useEffect(() => {
    if (overviewRowForAssignment?.status) {
      setAssignmentStatus(overviewRowForAssignment.status as AssignmentStatus);
    }
  }, [overviewRowForAssignment?.status]);

  useEffect(() => {
    const run = async () => {
      const storedFeedback = sessionStorage.getItem('relopass_hr_notes') || '';
      const hydrateFeedback = (raw: string) => {
        if (!raw) return;
        try {
          const parsed = JSON.parse(raw);
          const notes = typeof parsed?.notes === 'string' ? parsed.notes : '';
          const sections = Array.isArray(parsed?.requestedSections)
            ? parsed.requestedSections.filter((s: any) => typeof s === 'string')
            : [];
          setHrFeedback(notes || raw);
          setHrRequestedSections(sections);
        } catch {
          setHrFeedback(raw);
          setHrRequestedSections([]);
        }
      };

      if (storedFeedback) {
        hydrateFeedback(storedFeedback);
        return;
      }
      if (overviewRowForAssignment?.status !== 'awaiting_intake' || !assignmentId) return;
      try {
        const journey = await employeeAPI.getNextQuestion(assignmentId);
        if (journey.hrNotes) hydrateFeedback(journey.hrNotes);
      } catch {
        // best effort
      }
    };
    void run();
  }, [assignmentId, overviewRowForAssignment?.status]);

  useEffect(() => {
    if (!assignmentId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await employeeAPI.getFeedback(assignmentId);
        if (!cancelled && data) {
          setCaseFeedback(data.map((f) => ({ id: f.id, message: f.message, created_at: f.created_at })));
        }
      } catch {
        if (!cancelled) setCaseFeedback([]);
      }
    })();
    return () => { cancelled = true; };
  }, [assignmentId]);

  const handleSave = async (nextDraft: CaseDraftDTO): Promise<string> => {
    let caseIdToSave = resolvedCaseId;
    if (!caseIdToSave && assignmentIdFromRoute) {
      const { data, error: loadError } = await getCaseDetailsByAssignmentId(assignmentIdFromRoute);
      if (loadError || !data?.case?.id) {
        throw new Error("Couldn't find your case. Refresh and try again.");
      }
      caseIdToSave = data.case.id;
      setResolvedCaseId(caseIdToSave);
    }
    if (!caseIdToSave) {
      throw new Error("Couldn't find your case. Refresh and try again.");
    }
    const nextJson = JSON.stringify(nextDraft);
    if (lastSavedDraftJsonRef.current === nextJson) {
      return caseIdToSave;
    }
    const updated = await patchCase(caseIdToSave, nextDraft);
    const merged = caseToWizardDraft(updated);
    setDraft(merged);
    setCaseData(updated);
    lastSavedDraftJsonRef.current = JSON.stringify(merged);
    setError('');
    return caseIdToSave;
  };

  const handleNext = async (nextDraft: CaseDraftDTO) => {
    if (!assignmentId) {
      setError('Assignment not found. Refresh and try again.');
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      const caseIdAfterSave = await handleSave(nextDraft);
      if (currentStep === 1 && caseIdAfterSave) {
        try {
          await startResearch(caseIdAfterSave);
          setBanner('Pulling destination requirements - shown in Step 5.');
        } catch {
          // Research is non-blocking; continue to next step
        }
      }
      await loadRequirements();
      if (currentStep === 4 && assignmentId) {
        notifyHrEmployeeSaved(assignmentId).catch(() => {});
      }
      navigate(`/employee/case/${assignmentId}/wizard/${currentStep + 1}`);
    } catch (err: any) {
      setError(err?.message || "Couldn't save. Try again.");
      // Do not navigate on save failure: user stays on current step
    } finally {
      setIsSaving(false);
    }
  };

  const handleBack = () => {
    if (!assignmentId) return;
    navigate(`/employee/case/${assignmentId}/wizard/${currentStep - 1}`);
  };

  const handleFillForTest = async () => {
    if (!assignmentId) return;
    setError('');
    const baseDraft = caseToWizardDraft(caseData);
    const empName =
      linkedSummaries.find((r) => r.assignment_id === assignmentId)?.company?.name?.trim() || null;
    const nextDraft = buildTestDraft(assignmentId, baseDraft, empName);
    setIsSaving(true);
    try {
      await handleSave(nextDraft);
    } catch (err: any) {
      setError(err?.message || 'Unable to apply test data.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleClassify = async () => {
    if (!resolvedCaseId) return;
    setIsClassifying(true);
    try {
      const res = await classifyRelocationCase(resolvedCaseId);
      setNextActions(res.classification.next_actions || []);
    } catch (err: any) {
      setError(err?.message || 'Unable to generate next steps.');
    } finally {
      setIsClassifying(false);
    }
  };

  const onSaveForSteps = useCallback(async (draft: CaseDraftDTO): Promise<void> => {
    await handleSave(draft);
  }, [handleSave]);

  const stepProps = {
    caseId: resolvedCaseId || assignmentId || '',
    draft: displayDraft,
    requiredFields,
    onSave: onSaveForSteps,
    onNext: handleNext,
    onBack: handleBack,
    onGoToStep: (stepNumber: number) =>
      assignmentId && navigate(`/employee/case/${assignmentId}/wizard/${stepNumber}`),
    isSaving,
    preFilled,
  };

  const stepNode = useMemo(() => {
    if (currentStep === 1) return <Step1RelocationBasics {...stepProps} banner={banner} />;
    if (currentStep === 2) return <Step2EmployeeProfile {...stepProps} />;
    if (currentStep === 3) return <Step3FamilyMembers {...stepProps} />;
    if (currentStep === 4) return <Step4AssignmentContext {...stepProps} />;
    return <Step5ReviewCreate {...stepProps} />;
  }, [currentStep, draft, requiredFields, banner, isSaving]);

  const completedSteps = stepCompletion.completed;

  // Sprint 2: docked shell + trigger-only FAB.
  const [assistantOpen, setAssistantOpen] = useState(false);

  return (
    <AppShell title="My case" subtitle="Relocation intake wizard.">
      <PolicyAssistantDockedShell
        open={assistantOpen}
        onOpenChange={setAssistantOpen}
        title="Ask about your policy"
        subtitle="Bounded Q&A on your published policy."
        titleId="employee-wizard-assistant-shell-title"
        assistant={() => (
          <EmployeePolicyAssistantPanel
            assignmentId={assignmentId}
            assignmentLoading={false}
            variant="embedded"
          />
        )}
      >
      <div className="max-w-6xl mx-auto space-y-6">
        {assignmentStatus === 'awaiting_intake' && hrFeedback && (
          <div className="rounded-lg border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]">
            <div className="font-semibold">Changes requested by HR</div>
            {hrRequestedSections.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {hrRequestedSections.map((section) => (
                  <Button unstyled
                    key={section}
                    className="rounded-full border border-[#f59e0b] bg-white px-3 py-1 text-[11px] font-semibold text-[#92400e]"
                    onClick={() => {
                      const map: Record<string, number> = {
                        'Relocation Basics': 1,
                        'Employee Profile': 2,
                        'Family Members': 3,
                        'Assignment / Context': 4,
                      };
                      const stepToOpen = map[section] || 1;
                      navigate(`/employee/case/${assignmentId}/wizard/${stepToOpen}`);
                    }}
                  >
                    Fix: {section}
                  </Button>
                ))}
              </div>
            )}
            <div className="mt-2 text-xs text-[#92400e] whitespace-pre-wrap">{hrFeedback}</div>
          </div>
        )}
        {error && (
          <div className="rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
            {error}
            {import.meta.env.DEV && assignmentId && (
              <div className="mt-2 text-xs font-mono text-[#6b7280]">assignmentId: {assignmentId}</div>
            )}
          </div>
        )}
        {caseFeedback.length > 0 && (
          <Card padding="md">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">HR Feedback</div>
            <div className="space-y-3 text-sm">
              {caseFeedback.map((f) => (
                <div key={f.id} className="border-l-2 border-[#0b2b43] pl-3">
                  <div className="text-xs text-[#6b7280]">
                    {new Date(f.created_at).toLocaleString()}
                  </div>
                  <div className="text-[#0b2b43] mt-0.5">{f.message}</div>
                </div>
              ))}
            </div>
          </Card>
        )}
        {caseHydrating && (
          <div
            className="rounded-lg border border-[#e2e8f0] bg-white px-4 py-3 text-sm text-[#0b2b43]"
            role="status"
            aria-live="polite"
            aria-busy="true"
          >
            Restoring your saved details…
          </div>
        )}
        <CaseContextBar
          origin={caseData?.originCountry}
          destination={caseData?.destCountry}
          familyCount={(draft.familyMembers.children?.length || 0) + (draft.familyMembers.spouse ? 1 : 0)}
          targetDate={draft.relocationBasics.targetMoveDate}
          stage={`Step ${currentStep} of 5`}
        />
        {(requiredFields.length > 0 || nextActions.length > 0) && (
          <Card padding="md">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[#0b2b43]">Next actions</div>
                <div className="text-xs text-[#6b7280]">
                  Complete these items to keep your case moving.
                </div>
              </div>
              <Button unstyled
                onClick={handleClassify}
                disabled={isClassifying}
                className="rounded-full border border-[#0b2b43] px-3 py-1 text-xs font-semibold text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white disabled:opacity-60"
              >
                {isClassifying ? 'Generating...' : 'Generate next steps'}
              </Button>
            </div>
            <ul className="mt-3 space-y-2 text-sm text-[#1f2937]">
              {nextActions.length > 0 ? (
                nextActions.map((action) => (
                  <li key={action.key} className="flex items-center justify-between">
                    <span>{action.label}</span>
                    <span className="text-[11px] uppercase tracking-wide text-[#6b7280]">
                      {action.priority}
                    </span>
                  </li>
                ))
              ) : (
                <li className="text-xs text-[#6b7280]">No next actions yet.</li>
              )}
            </ul>
          </Card>
        )}

        <div className="space-y-6">
          <WizardStepRail
            currentStep={currentStep}
            completedSteps={completedSteps}
            maxUnlocked={stepCompletion.maxUnlocked}
            onSelect={(stepNumber) => {
              if (stepNumber > stepCompletion.maxUnlocked) {
                setError('Complete the previous steps first.');
                return;
              }
              navigate(`/employee/case/${assignmentId}/wizard/${stepNumber}`);
            }}
          />
          <div>
            {caseHydrating ? (
              <Card padding="lg" className="min-h-[280px]">
                <div className="text-sm font-medium text-[#0b2b43] mb-1">Restoring your answers…</div>
                <p className="text-xs text-[#6b7280] mb-4">
                  Loading saved progress for this assignment. You can move through steps once data is ready.
                </p>
                <div className="space-y-3 animate-pulse" aria-hidden>
                  <div className="h-10 rounded-md bg-[#e2e8f0]" />
                  <div className="h-10 rounded-md bg-[#e2e8f0]" />
                  <div className="h-36 rounded-md bg-[#e2e8f0]" />
                </div>
              </Card>
            ) : (
              stepNode
            )}
          </div>
          <Card padding="md">
            <div className="text-sm font-semibold text-[#0b2b43]">Need help?</div>
            <div className="text-xs text-[#6b7280] mt-1">Our team can guide you through the wizard.</div>
            <Button unstyled className="mt-3 text-xs text-[#0b2b43] underline">Contact support</Button>
            {enableTestFill && (
              <div className="mt-4 border-t border-[#e2e8f0] pt-3">
                <Button unstyled
                  type="button"
                  onClick={handleFillForTest}
                  title="Demo only — fills the wizard with deterministic answers."
                  className="text-xs text-[#94a3b8] hover:text-[#0b2b43] hover:underline"
                >
                  Fill for test (demo)
                </Button>
              </div>
            )}
          </Card>
        </div>
      </div>
      </PolicyAssistantDockedShell>
      {/* FAB trigger — toggles the docked shell. Hides on lg+ when
          open so it doesn't overlap the panel. */}
      <PolicyAssistantFab
        label="Ask about your policy"
        isPanelOpen={assistantOpen}
        onClick={() => setAssistantOpen((v) => !v)}
      />
    </AppShell>
  );
};
