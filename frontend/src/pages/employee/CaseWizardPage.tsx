import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ROUTES } from '../../routes';
import { CaseContextBar } from '../../components/case/CaseContextBar';
import { WizardSidebar } from '../../components/case/WizardSidebar';
import { Card } from '../../components/antigravity';
import { getCase, getRequirements, patchCase, startResearch } from '../../api/cases';
import type { CaseDTO, CaseDraftDTO } from '../../types';
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

  const stepFromRoute = step ? Number(step) : location.pathname.endsWith('/review') ? 5 : 1;
  const currentStep = Math.min(5, Math.max(1, stepFromRoute));

  const loadCase = async () => {
    if (!caseId) return;
    try {
      const data = await getCase(caseId);
      setCaseData(data);
      setDraft(data.draft || defaultDraft);
    } catch {
      const data = await patchCase(caseId, defaultDraft);
      setCaseData(data);
      setDraft(data.draft || defaultDraft);
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

  const handleSave = async (nextDraft: CaseDraftDTO) => {
    if (!caseId) return;
    try {
      const updated = await patchCase(caseId, nextDraft);
      setDraft(updated.draft);
      setCaseData(updated);
      await loadRequirements();
      setError('');
    } catch (err: any) {
      setError(err?.message || 'Unable to save draft.');
      throw err;
    }
  };

  const handleNext = async (nextDraft: CaseDraftDTO) => {
    if (!caseId) return;
    try {
      await handleSave(nextDraft);
      if (currentStep === 1) {
        await startResearch(caseId);
        setBanner('Pulling destination requirements—shown in Step 5.');
      }
      navigate(`/employee/case/${caseId}/wizard/${currentStep + 1}`);
    } catch {
      // error already set in handleSave
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

  const completedSteps = Array.from({ length: currentStep - 1 }).map((_, idx) => idx + 1);

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
              onSelect={(stepNumber) => navigate(`/employee/case/${caseId}/wizard/${stepNumber}`)}
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
