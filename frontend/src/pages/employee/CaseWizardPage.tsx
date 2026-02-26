import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { CaseContextBar } from '../../components/case/CaseContextBar';
import { WizardSidebar } from '../../components/case/WizardSidebar';
import { Card } from '../../components/antigravity';
import { getCaseDetailsByAssignmentId } from '../../api/caseDetails';
import { patchCase, startResearch } from '../../api/cases';
import { notifyHrEmployeeSaved } from '../../api/notifications';
import { buildNextActionsFromMissingFields, classifyRelocationCase, getRelocationCase } from '../../api/relocation';
import { employeeAPI } from '../../api/client';
import { getAuthItem } from '../../utils/demo';
import type { AssignmentStatus, CaseDTO, CaseDraftDTO, NextAction } from '../../types';
import { Step1RelocationBasics } from './wizard/Step1RelocationBasics';
import { Step2EmployeeProfile } from './wizard/Step2EmployeeProfile';
import { Step3FamilyMembers } from './wizard/Step3FamilyMembers';
import { Step4AssignmentContext } from './wizard/Step4AssignmentContext';
import { Step5ReviewCreate } from './wizard/Step5ReviewCreate';

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

function caseToWizardDraft(caseData: CaseDTO | null): CaseDraftDTO {
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

  return {
    relocationBasics: {
      ...base.relocationBasics,
      ...legacyBasics,
      ...(caseData.draft?.relocationBasics || {}),
    },
    employeeProfile: {
      ...base.employeeProfile,
      ...(caseData.draft?.employeeProfile || {}),
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

const COUNTRY_OPTIONS = [
  { name: 'Norway', cities: ['Oslo', 'Bergen'] },
  { name: 'Singapore', cities: ['Singapore'] },
  { name: 'United States', cities: ['New York', 'San Francisco'] },
  { name: 'United Kingdom', cities: ['London', 'Manchester'] },
  { name: 'Germany', cities: ['Berlin', 'Munich'] },
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

const buildTestDraft = (seedKey: string, baseDraft: CaseDraftDTO): CaseDraftDTO => {
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
      employerName: 'ReloPass Demo Co',
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

  // Enforce linear progression: cannot skip ahead.
  useEffect(() => {
    if (!assignmentId) return;
    if (currentStep > stepCompletion.maxUnlocked) {
      setError('Please complete the previous steps before continuing.');
      navigate(`/employee/case/${assignmentId}/wizard/${stepCompletion.maxUnlocked}`, { replace: true });
    }
  }, [assignmentId, currentStep, stepCompletion.maxUnlocked, navigate]);

  const loadCase = async () => {
    if (!assignmentIdFromRoute) return;
    try {
      const { data, error: loadError } = await getCaseDetailsByAssignmentId(assignmentIdFromRoute);
      if (loadError || !data) {
        setCaseData(null);
        setDraft(buildDefaultDraft());
        setResolvedCaseId(null);
        if (loadError) setError(loadError.includes('Case row missing') ? loadError : 'Assignment not found or not visible under RLS.');
      } else {
        setCaseData(data.case);
        setDraft(caseToWizardDraft(data.case));
        setResolvedCaseId(data.case.id);
      }
    } catch {
      setCaseData(null);
      setDraft(buildDefaultDraft());
      setResolvedCaseId(null);
      setError('Assignment not found or not visible under RLS.');
    }
  };

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
    loadCase();
  }, [assignmentIdFromRoute]);

  useEffect(() => {
    if (resolvedCaseId || assignmentIdFromRoute) loadRequirements();
  }, [resolvedCaseId, assignmentIdFromRoute, loadRequirements]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    if (!caseData) return;
    console.debug('Wizard defaults (relocationBasics):', caseToWizardDraft(caseData).relocationBasics);
  }, [caseData?.id, caseData?.updatedAt]);

  // Route gating: the wizard is only for intake / changes-requested.
  useEffect(() => {
    const run = async () => {
      try {
        const res = await employeeAPI.getCurrentAssignment();
        const assignment = res.assignment;
        if (!assignment) return;
        if (assignmentId && assignment.id !== assignmentId) return;
        setAssignmentStatus(assignment.status as AssignmentStatus);

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
        } else if (assignment.status === 'awaiting_intake' && assignmentId) {
          // If the employee opened the wizard directly, pull HR notes from journey API.
          const journey = await employeeAPI.getNextQuestion(assignmentId);
          if (journey.hrNotes) hydrateFeedback(journey.hrNotes);
        }

        const isSubmitted =
          assignment.status === 'submitted' ||
          assignment.status === 'approved' ||
          assignment.status === 'rejected' ||
          assignment.status === 'closed';
        if (isSubmitted) {
          setAssignmentStatus(assignment.status as AssignmentStatus);
        }
      } catch {
        // Best effort; wizard can still function for MVP draft creation.
      }
    };
    run();
  }, [assignmentId, navigate]);

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

  const handleSave = async (nextDraft: CaseDraftDTO) => {
    if (!resolvedCaseId) return;
    const updated = await patchCase(resolvedCaseId, nextDraft);
    setDraft(caseToWizardDraft(updated));
    setCaseData(updated);
    await loadRequirements();
    setError('');
    if (assignmentId) {
      notifyHrEmployeeSaved(assignmentId).catch(() => {});
    }
  };

  const handleNext = async (nextDraft: CaseDraftDTO) => {
    if (!resolvedCaseId || !assignmentId) return;
    try {
      await handleSave(nextDraft);
      if (currentStep === 1) {
        try {
          await startResearch(resolvedCaseId);
          setBanner('Pulling destination requirements—shown in Step 5.');
        } catch {
          // Research is non-blocking; continue to next step
        }
      }
      navigate(`/employee/case/${assignmentId}/wizard/${currentStep + 1}`);
    } catch (err: any) {
      setError(err?.message || 'Unable to save. Please try again.');
    }
  };

  const handleBack = () => {
    if (!assignmentId) return;
    navigate(`/employee/case/${assignmentId}/wizard/${currentStep - 1}`);
  };

  const handleFillForTest = async () => {
    if (!resolvedCaseId || !assignmentId) return;
    setError('');
    const baseDraft = caseToWizardDraft(caseData);
    const nextDraft = buildTestDraft(assignmentId, baseDraft);
    try {
      await handleSave(nextDraft);
    } catch (err: any) {
      setError(err?.message || 'Unable to apply test data.');
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

  const stepProps = {
    caseId: resolvedCaseId || assignmentId || '',
    assignmentId: assignmentId || null,
    draft,
    requiredFields,
    onSave: handleSave,
    onNext: handleNext,
    onBack: handleBack,
    onGoToStep: (stepNumber: number) =>
      assignmentId && navigate(`/employee/case/${assignmentId}/wizard/${stepNumber}`),
  };

  const stepNode = useMemo(() => {
    if (currentStep === 1) return <Step1RelocationBasics {...stepProps} banner={banner} />;
    if (currentStep === 2) return <Step2EmployeeProfile {...stepProps} />;
    if (currentStep === 3) return <Step3FamilyMembers {...stepProps} />;
    if (currentStep === 4) return <Step4AssignmentContext {...stepProps} />;
    return <Step5ReviewCreate {...stepProps} />;
  }, [currentStep, draft, requiredFields, banner]);

  const completedSteps = stepCompletion.completed;

  return (
    <AppShell title="My Case" subtitle="Complete your relocation intake.">
      <div className="max-w-6xl mx-auto space-y-6">
        {assignmentStatus === 'awaiting_intake' && hrFeedback && (
          <div className="rounded-lg border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]">
            <div className="font-semibold">Changes requested by HR</div>
            {hrRequestedSections.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {hrRequestedSections.map((section) => (
                  <button
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
                  </button>
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
        {enableTestFill && (
          <Card padding="md">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[#0b2b43]">Test controls</div>
                <div className="text-xs text-[#6b7280]">Generate deterministic answers for demos.</div>
              </div>
              <button
                onClick={handleFillForTest}
                className="rounded-full border border-[#0b2b43] px-3 py-1 text-xs font-semibold text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white"
              >
                Fill for test
              </button>
            </div>
          </Card>
        )}

        <CaseContextBar
          origin={caseData?.originCountry}
          destination={caseData?.destCountry}
          familyCount={(draft.familyMembers.children?.length || 0) + (draft.familyMembers.spouse ? 1 : 0) + 1}
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
              <button
                onClick={handleClassify}
                disabled={isClassifying}
                className="rounded-full border border-[#0b2b43] px-3 py-1 text-xs font-semibold text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white disabled:opacity-60"
              >
                {isClassifying ? 'Generating...' : 'Generate next steps'}
              </button>
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

        <div className="grid grid-cols-1 lg:grid-cols-[260px,1fr] gap-6">
          <div className="space-y-6">
            <WizardSidebar
              currentStep={currentStep}
              completedSteps={completedSteps}
              onSelect={(stepNumber) => {
                if (stepNumber > stepCompletion.maxUnlocked) {
                  setError('Complete the previous steps first.');
                  return;
                }
                navigate(`/employee/case/${assignmentId}/wizard/${stepNumber}`);
              }}
            />
            <Card padding="md">
              <div className="text-sm font-semibold text-[#0b2b43]">Need help?</div>
              <div className="text-xs text-[#6b7280] mt-1">Our team can guide you through the wizard.</div>
              <button className="mt-3 text-xs text-[#0b2b43] underline">Contact support</button>
            </Card>
          </div>
          <div>{stepNode}</div>
        </div>
      </div>
    </AppShell>
  );
};
