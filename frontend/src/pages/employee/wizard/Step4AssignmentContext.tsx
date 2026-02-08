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
  const [error, setError] = useState('');

  const update = (key: keyof typeof local, value: any) => {
    setLocal({ ...local, [key]: value });
  };

  const nextDraft: CaseDraftDTO = { ...draft, assignmentContext: local };
  const employerMissing = !local.employerName;
  const jobTitleMissing = !local.jobTitle;
  const contractStartMissing = !local.contractStartDate;
  const contractTypeMissing = !local.contractType;
  const salaryBandMissing = !local.salaryBand;
  const hasMissing =
    employerMissing || jobTitleMissing || contractStartMissing || contractTypeMissing || salaryBandMissing;

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Assignment / Context</div>
      <div className="text-sm text-[#6b7280] mt-1">Provide assignment details to tailor requirements.</div>
      {error && (
        <div className="mt-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="text-sm text-[#0b2b43]">
          Employer name
          {(isRequired(requiredFields, 'assignmentContext.employerName') || true) && employerMissing && (
            <span className="text-red-600"> *</span>
          )}
          <input
            value={local.employerName || ''}
            onChange={(event) => update('employerName', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            placeholder="Provided by HR"
            disabled={!employerMissing}
          />
          <div className="text-xs text-[#6b7280] mt-1">
            {employerMissing ? 'If blank, ask HR to provide the employer name.' : 'Provided by HR'}
          </div>
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
          Job title
          {(isRequired(requiredFields, 'assignmentContext.jobTitle') || true) && jobTitleMissing && (
            <span className="text-red-600"> *</span>
          )}
          <input
            value={local.jobTitle || ''}
            onChange={(event) => update('jobTitle', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Contract start date
          {(isRequired(requiredFields, 'assignmentContext.contractStartDate') || true) && contractStartMissing && (
            <span className="text-red-600"> *</span>
          )}
          <input
            type="date"
            value={local.contractStartDate || ''}
            onChange={(event) => update('contractStartDate', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Contract type
          {(isRequired(requiredFields, 'assignmentContext.contractType') || true) && contractTypeMissing && (
            <span className="text-red-600"> *</span>
          )}
          <select
            value={local.contractType || ''}
            onChange={(event) => update('contractType', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          >
            <option value="">Select</option>
            <option value="permanent">Permanent</option>
            <option value="assignment">Assignment</option>
            <option value="contract">Contract</option>
          </select>
        </label>
        <label className="text-sm text-[#0b2b43]">
          Salary band
          {(isRequired(requiredFields, 'assignmentContext.salaryBand') || true) && salaryBandMissing && (
            <span className="text-red-600"> *</span>
          )}
          <select
            value={local.salaryBand || ''}
            onChange={(event) => update('salaryBand', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          >
            <option value="">Select</option>
            <option value="50–100 k€">50–100 k€</option>
            <option value="100–150 k€">100–150 k€</option>
            <option value="150–200 k€">150–200 k€</option>
            <option value="200–300 k€">200–300 k€</option>
            <option value="300k€+">300k€+</option>
          </select>
        </label>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={async () => {
              await onSave(nextDraft);
              window.location.href = '/employee/journey';
            }}
          >
            Save as draft & exit
          </Button>
          <Button
            onClick={() => {
              if (hasMissing) {
                setError('Please complete all required fields (marked with *).');
                return;
              }
              setError('');
              onNext(nextDraft);
            }}
          >
            Next
          </Button>
        </div>
      </div>
    </Card>
  );
};
