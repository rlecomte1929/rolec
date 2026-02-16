import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ROUTES } from '../../routes';
import { CaseContextBar } from '../../components/case/CaseContextBar';
import { WizardSidebar } from '../../components/case/WizardSidebar';
import { Card } from '../../components/antigravity';
import { getCase, getRequirements, patchCase, startResearch } from '../../api/cases';
import { employeeAPI } from '../../api/client';
import type { AssignmentStatus, CaseDTO, CaseDraftDTO } from '../../types';
import { Step1RelocationBasics } from './wizard/Step1RelocationBasics';
import { Step2EmployeeProfile } from './wizard/Step2EmployeeProfile';
import { Step3FamilyMembers } from './wizard/Step3FamilyMembers';
import { Step4AssignmentContext } from './wizard/Step4AssignmentContext';
import { Step5ReviewCreate } from './wizard/Step5ReviewCreate';

const defaultDraft: CaseDraftDTO = {
  relocationBasics: {},
  employeeProfile: {},
  familyMembers: {},
  assignmentContext: {},
};

export const CaseWizardPage: React.FC = () => {
  const { caseId, step } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [draft, setDraft] = useState<CaseDraftDTO>(defaultDraft);
  const [caseData, setCaseData] = useState<CaseDTO | null>(null);
  const [requiredFields, setRequiredFields] = useState<string[]>([]);
  const [banner, setBanner] = useState('');
  const [error, setError] = useState('');
  const [assignmentStatus, setAssignmentStatus] = useState<AssignmentStatus | null>(null);
  const [hrFeedback, setHrFeedback] = useState<string>('');
  const [hrRequestedSections, setHrRequestedSections] = useState<string[]>([]);

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

  // Enforce linear progression: cannot skip ahead.
  useEffect(() => {
    if (!caseId) return;
    if (currentStep > stepCompletion.maxUnlocked) {
      setError('Please complete the previous steps before continuing.');
      navigate(`/employee/case/${caseId}/wizard/${stepCompletion.maxUnlocked}`, { replace: true });
    }
  }, [caseId, currentStep, stepCompletion.maxUnlocked, navigate]);

  const loadCase = async () => {
    if (!caseId) return;
    try {
      const data = await getCase(caseId);
      setCaseData(data);
      setDraft(data.draft || defaultDraft);
    } catch {
      try {
        const data = await patchCase(caseId, defaultDraft);
        setCaseData(data);
        setDraft(data.draft || defaultDraft);
      } catch (err: any) {
        setError(err?.message || 'Unable to load or create your case. Please try again.');
      }
    }
  };

  const loadRequirements = async () => {
    if (!caseId) return;
    try {
      const data = await getRequirements(caseId);
      const fields = data.requirements.flatMap((req) => req.requiredFields);
      setRequiredFields(fields);
    } catch {
      setRequiredFields([]);
    }
  };

  useEffect(() => {
    loadCase();
    loadRequirements();
  }, [caseId]);

  // Route gating: the wizard is only for intake / changes-requested.
  useEffect(() => {
    const run = async () => {
      try {
        const res = await employeeAPI.getCurrentAssignment();
        const assignment = res.assignment;
        if (!assignment) return;
        if (caseId && assignment.id !== caseId) return;
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
        } else if (assignment.status === 'CHANGES_REQUESTED' && caseId) {
          // If the employee opened the wizard directly, pull HR notes from journey API.
          const journey = await employeeAPI.getNextQuestion(caseId);
          if (journey.hrNotes) hydrateFeedback(journey.hrNotes);
        }

        const isSubmitted =
          assignment.status === 'EMPLOYEE_SUBMITTED' ||
          assignment.status === 'HR_REVIEW' ||
          assignment.status === 'HR_APPROVED';
        if (isSubmitted) {
          navigate(ROUTES.EMP_DASH, { replace: true });
        }
      } catch {
        // Best effort; wizard can still function for MVP draft creation.
      }
    };
    run();
  }, [caseId, navigate]);

  const handleSave = async (nextDraft: CaseDraftDTO) => {
    if (!caseId) return;
    const updated = await patchCase(caseId, nextDraft);
    setDraft(updated.draft);
    setCaseData(updated);
    await loadRequirements();
    setError('');
  };

  const handleNext = async (nextDraft: CaseDraftDTO) => {
    if (!caseId) return;
    try {
      await handleSave(nextDraft);
      if (currentStep === 1) {
        try {
          await startResearch(caseId);
          setBanner('Pulling destination requirements—shown in Step 5.');
        } catch {
          // Research is non-blocking; continue to next step
        }
      }
      navigate(`/employee/case/${caseId}/wizard/${currentStep + 1}`);
    } catch (err: any) {
      setError(err?.message || 'Unable to save. Please try again.');
    }
  };

  const handleBack = () => {
    if (!caseId) return;
    navigate(`/employee/case/${caseId}/wizard/${currentStep - 1}`);
  };

  const stepProps = {
    caseId: caseId || '',
    draft,
    requiredFields,
    onSave: handleSave,
    onNext: handleNext,
    onBack: handleBack,
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
    <div className="min-h-screen bg-[#f5f7fa] text-[#1f2937]">
      <header className="bg-white border-b border-[#e2e8f0]">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="text-lg font-semibold text-[#0b2b43]">ReloPass</div>
          <nav className="flex items-center gap-4 text-sm text-[#6b7280]">
            <Link to={ROUTES.EMP_DASH} className="hover:text-[#0b2b43]">Dashboard</Link>
            <Link to={`/employee/case/${caseId}/wizard/1`} className="text-[#0b2b43] font-semibold">My Case</Link>
            <Link to="#" className="hover:text-[#0b2b43]">Providers</Link>
            <Link to="/hr/policy" className="hover:text-[#0b2b43]">HR Policy</Link>
            <Link to="/messages" className="hover:text-[#0b2b43]">Messages</Link>
            <Link to="/resources" className="hover:text-[#0b2b43]">Resources</Link>
          </nav>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        {assignmentStatus === 'CHANGES_REQUESTED' && hrFeedback && (
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
                      navigate(`/employee/case/${caseId}/wizard/${stepToOpen}`);
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
          </div>
        )}
        <CaseContextBar
          origin={caseData?.originCountry}
          destination={caseData?.destCountry}
          familyCount={(draft.familyMembers.children?.length || 0) + (draft.familyMembers.spouse ? 1 : 0) + 1}
          targetDate={draft.relocationBasics.targetMoveDate}
          stage={`Step ${currentStep} of 5`}
        />

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
                navigate(`/employee/case/${caseId}/wizard/${stepNumber}`);
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
    </div>
  );
};
