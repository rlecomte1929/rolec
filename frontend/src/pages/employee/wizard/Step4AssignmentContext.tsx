import React, { useState } from 'react';
import { Button, Card } from '../../../components/antigravity';
import type { CaseDraftDTO } from '../../../types';

interface StepProps {
  draft: CaseDraftDTO;
  requiredFields: string[];
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
  onBack: () => void;
}

const isRequired = (requiredFields: string[], key: string) => requiredFields.includes(key);

export const Step4AssignmentContext: React.FC<StepProps> = ({ draft, requiredFields, onSave, onNext, onBack }) => {
  const [local, setLocal] = useState(draft.assignmentContext);

  const update = (key: keyof typeof local, value: any) => {
    setLocal({ ...local, [key]: value });
  };

  const nextDraft: CaseDraftDTO = { ...draft, assignmentContext: local };

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Assignment / Context</div>
      <div className="text-sm text-[#6b7280] mt-1">Provide assignment details to tailor requirements.</div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="text-sm text-[#0b2b43]">
          Employer name{isRequired(requiredFields, 'assignmentContext.employerName') && ' *'}
          <input
            value={local.employerName || ''}
            onChange={(event) => update('employerName', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            placeholder="Provided by HR"
            disabled
          />
          <div className="text-xs text-[#6b7280] mt-1">Provided by HR</div>
        </label>
        <label className="text-sm text-[#0b2b43]">
          Employer country
          <input
            value={local.employerCountry || ''}
            onChange={(event) => update('employerCountry', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Job title{isRequired(requiredFields, 'assignmentContext.jobTitle') && ' *'}
          <input
            value={local.jobTitle || ''}
            onChange={(event) => update('jobTitle', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Contract start date{isRequired(requiredFields, 'assignmentContext.contractStartDate') && ' *'}
          <input
            type="date"
            value={local.contractStartDate || ''}
            onChange={(event) => update('contractStartDate', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Contract type
          <input
            value={local.contractType || ''}
            onChange={(event) => update('contractType', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Salary band
          <input
            value={local.salaryBand || ''}
            onChange={(event) => update('salaryBand', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={async () => {
              await onSave(nextDraft);
              window.location.href = '/employee/dashboard';
            }}
          >
            Save as draft & exit
          </Button>
          <Button onClick={() => onNext(nextDraft)}>Next</Button>
        </div>
      </div>
    </Card>
  );
};
