import React, { useState } from 'react';
import { Button, Card } from '../../../components/antigravity';
import type { CaseDraftDTO, FamilyMemberDTO } from '../../../types';

interface StepProps {
  draft: CaseDraftDTO;
  requiredFields: string[];
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
  onBack: () => void;
}

const isRequired = (requiredFields: string[], key: string) => requiredFields.includes(key);

export const Step3FamilyMembers: React.FC<StepProps> = ({ draft, requiredFields, onSave, onNext, onBack }) => {
  const [local, setLocal] = useState({
    ...draft.familyMembers,
    maritalStatus: draft.familyMembers.maritalStatus || 'Single',
  });
  const [children, setChildren] = useState<FamilyMemberDTO[]>(local.children || []);

  const update = (key: keyof typeof local, value: any) => {
    setLocal({ ...local, [key]: value });
  };

  const updateChild = (index: number, key: keyof FamilyMemberDTO, value: any) => {
    const next = [...children];
    next[index] = { ...next[index], [key]: value };
    setChildren(next);
  };

  const nextDraft: CaseDraftDTO = { ...draft, familyMembers: { ...local, children } };
  const maritalMissing = !local.maritalStatus;
  const hasDependents = Boolean(draft.relocationBasics?.hasDependents);
  const hasAnyDependent = Boolean(local.spouse?.fullName || children.some((c) => c.fullName));
  const dependentsMissing = hasDependents && !hasAnyDependent;
  const [error, setError] = useState('');

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Family Members</div>
      <div className="text-sm text-[#6b7280] mt-1">Add spouse and dependent information if applicable.</div>
      {error && (
        <div className="mt-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}

      <div className="mt-6 space-y-4">
        <label className="text-sm text-[#0b2b43]">
          Marital status
          {(isRequired(requiredFields, 'familyMembers.maritalStatus') || true) && maritalMissing && (
            <span className="text-red-600"> *</span>
          )}
          <select
            value={local.maritalStatus || ''}
            onChange={(event) => update('maritalStatus', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          >
            <option value="Single">Single</option>
            <option value="Married">Married</option>
            <option value="Partnership">Partnership</option>
            <option value="Divorced">Divorced</option>
            <option value="Widowed">Widowed</option>
          </select>
        </label>

        <div className="border border-[#e2e8f0] rounded-lg p-4">
          <div className="text-sm font-semibold text-[#0b2b43]">Spouse</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
            <label className="text-sm text-[#0b2b43]">
              Full name{isRequired(requiredFields, 'familyMembers.spouse.fullName') && ' *'}
              <input
                value={local.spouse?.fullName || ''}
                onChange={(event) => update('spouse', { ...local.spouse, fullName: event.target.value })}
                className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
              />
            </label>
            <label className="text-sm text-[#0b2b43]">
              Wants to work?
              <select
                value={local.spouse?.wantsToWork ? 'yes' : 'no'}
                onChange={(event) => update('spouse', { ...local.spouse, wantsToWork: event.target.value === 'yes' })}
                className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
              >
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
            </label>
          </div>
        </div>

        <div className="border border-[#e2e8f0] rounded-lg p-4">
          <div className="text-sm font-semibold text-[#0b2b43]">Children</div>
          {children.map((child, index) => (
            <div key={index} className="grid grid-cols-1 md:grid-cols-[1fr,1fr,1fr,auto] gap-3 mt-3 items-center">
              <input
                placeholder="Full name"
                value={child.fullName || ''}
                onChange={(event) => updateChild(index, 'fullName', event.target.value)}
                className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
              />
              <input
                type="date"
                value={child.dateOfBirth || ''}
                onChange={(event) => updateChild(index, 'dateOfBirth', event.target.value)}
                className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
              />
              <input
                placeholder="Nationality"
                value={child.nationality || ''}
                onChange={(event) => updateChild(index, 'nationality', event.target.value)}
                className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => setChildren(children.filter((_, idx) => idx !== index))}
              >
                Remove
              </Button>
            </div>
          ))}
          <div className="mt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setChildren([...children, {}])}
            >
              Add child
            </Button>
          </div>
        </div>
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
              if (maritalMissing) {
                setError('Please select a marital status.');
                return;
              }
              if (dependentsMissing) {
                setError('You marked “Relocating with dependents”. Please add at least a spouse or one child.');
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
