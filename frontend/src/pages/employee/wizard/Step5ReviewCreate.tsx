import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Alert } from '../../../components/antigravity';
import type { CaseDraftDTO, CaseRequirementsDTO, RequirementItemDTO } from '../../../types';
import { buildRequirementsFromMissingFields, getRelocationCase } from '../../../api/relocation';
import { RequirementList } from '../../../components/requirements/RequirementList';

interface StepProps {
  caseId: string;
  assignmentId?: string | null;
  draft: CaseDraftDTO;
  requiredFields: string[];
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
  onBack: () => void;
  onGoToStep?: (stepNumber: number) => void;
}

function SummarySection({
  title,
  stepNumber,
  onEdit,
  children,
}: {
  title: string;
  stepNumber: number;
  onEdit?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[#e2e8f0] bg-white p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-[#0b2b43]">{title}</div>
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="text-xs text-[#0b2b43] underline hover:no-underline"
          >
            Edit (Step {stepNumber})
          </button>
        )}
      </div>
      <div className="text-sm text-[#4b5563] space-y-1">{children}</div>
    </div>
  );
}

export const Step5ReviewCreate: React.FC<StepProps> = ({
  caseId,
  assignmentId,
  draft,
  onSave,
  onBack,
  onGoToStep,
}) => {
  const navigate = useNavigate();
  const [requirements, setRequirements] = useState<CaseRequirementsDTO | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    getRelocationCase(caseId)
      .then((relocation) =>
        setRequirements(buildRequirementsFromMissingFields(caseId, relocation.missing_fields || []))
      )
      .catch(() => setRequirements(null));
  }, [caseId]);

  const grouped = requirements?.requirements.reduce<Record<string, RequirementItemDTO[]>>((acc, item) => {
    acc[item.pillar] = acc[item.pillar] || [];
    acc[item.pillar].push(item);
    return acc;
  }, {}) || {};

  const handleSave = async () => {
    setError('');
    setIsSaving(true);
    try {
      await onSave(draft);
      setSaved(true);
    } catch (err: any) {
      const resData = err?.response?.data;
      const detail = err?.detail ?? resData?.detail;
      if (detail && typeof detail === 'object' && detail.message) {
        const missing = Array.isArray(detail.missingFields) ? detail.missingFields : [];
        setError(missing.length
          ? `${detail.message}. Please complete Step 1 (Relocation Basics) required fields.`
          : detail.message);
      } else if (detail && typeof detail === 'string') {
        setError(detail);
      } else if (resData && typeof resData === 'object' && resData.message) {
        setError(resData.message);
      } else {
        setError('Unable to save. Please try again.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Review & Save</div>
      {error && (
        <div className="mt-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}
      {saved && (
        <div className="mt-4">
          <Alert variant="success" title="Saved">
            Your data has been saved successfully. You can continue editing or go to the dashboard.
          </Alert>
        </div>
      )}

      <div className="text-sm text-[#6b7280] mt-1">
        Review the requirements generated from destination research. Save to persist your data.
      </div>

      <div className="mt-6">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Case overview — validate your responses</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SummarySection
            title="Relocation Basics"
            stepNumber={1}
            onEdit={onGoToStep ? () => onGoToStep(1) : undefined}
          >
            <div>Origin: {[draft.relocationBasics?.originCity, draft.relocationBasics?.originCountry].filter(Boolean).join(', ') || '—'}</div>
            <div>Destination: {[draft.relocationBasics?.destCity, draft.relocationBasics?.destCountry].filter(Boolean).join(', ') || '—'}</div>
            <div>Purpose: {draft.relocationBasics?.purpose || '—'}</div>
            <div>Target move date: {draft.relocationBasics?.targetMoveDate || '—'}</div>
            <div>Duration: {draft.relocationBasics?.durationMonths != null ? `${draft.relocationBasics.durationMonths} months` : '—'}</div>
          </SummarySection>
          <SummarySection
            title="Employee Profile"
            stepNumber={2}
            onEdit={onGoToStep ? () => onGoToStep(2) : undefined}
          >
            <div>Name: {draft.employeeProfile?.fullName || '—'}</div>
            <div>Email: {draft.employeeProfile?.email || '—'}</div>
            <div>Nationality: {draft.employeeProfile?.nationality || '—'}</div>
            <div>Passport: {draft.employeeProfile?.passportCountry || '—'}</div>
            <div>Residence: {draft.employeeProfile?.residenceCountry || '—'}</div>
          </SummarySection>
          <SummarySection
            title="Family Members"
            stepNumber={3}
            onEdit={onGoToStep ? () => onGoToStep(3) : undefined}
          >
            <div>Spouse: {draft.familyMembers?.spouse?.fullName || '—'}</div>
            <div>Children: {draft.familyMembers?.children?.length ? `${draft.familyMembers.children.length} child(ren)` : '—'}</div>
          </SummarySection>
          <SummarySection
            title="Assignment / Context"
            stepNumber={4}
            onEdit={onGoToStep ? () => onGoToStep(4) : undefined}
          >
            <div>Employer: {draft.assignmentContext?.employerName || '—'}</div>
            <div>Job title: {draft.assignmentContext?.jobTitle || '—'}</div>
            <div>Contract start: {draft.assignmentContext?.contractStartDate || '—'}</div>
            <div>Contract type: {draft.assignmentContext?.contractType || '—'}</div>
          </SummarySection>
        </div>
      </div>

      {localStorage.getItem('demo_role') === 'admin' && (
        <button
          className="mt-3 text-xs text-[#0b2b43] underline"
          onClick={() => navigate('/admin/countries')}
        >
          View Country Requirements DB
        </button>
      )}

      <div className="mt-6 space-y-6">
        {Object.entries(grouped).map(([pillar, items]) => (
          <div key={pillar}>
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">{pillar}</div>
            <RequirementList items={items} />
          </div>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save'}
        </Button>
        {saved && (
          <Button
            onClick={() =>
              assignmentId
                ? navigate(`/employee/case/${assignmentId}/summary`)
                : navigate('/employee/dashboard')
            }
          >
            Go to dashboard
          </Button>
        )}
      </div>
    </Card>
  );
};
