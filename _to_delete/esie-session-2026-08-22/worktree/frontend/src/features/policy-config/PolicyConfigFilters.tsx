import React from 'react';
import { Select } from '../../components/antigravity';
import {
  POLICY_ASSIGNMENT_TYPE_OPTIONS,
  POLICY_FAMILY_STATUS_OPTIONS,
} from './policyTargeting';

type Props = {
  assignmentType: string | null;
  familyStatus: string | null;
  onAssignmentType: (v: string | null) => void;
  onFamilyStatus: (v: string | null) => void;
  disabled?: boolean;
};

export const PolicyConfigFilters: React.FC<Props> = ({
  assignmentType,
  familyStatus,
  onAssignmentType,
  onFamilyStatus,
  disabled,
}) => {
  const atOpts = [
    { value: '', label: 'All assignment types' },
    ...POLICY_ASSIGNMENT_TYPE_OPTIONS.map((x) => ({ value: x.value, label: x.label })),
  ];
  const fsOpts = [
    { value: '', label: 'All family situations' },
    ...POLICY_FAMILY_STATUS_OPTIONS.map((x) => ({ value: x.value, label: x.label })),
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className={disabled ? 'opacity-60 pointer-events-none' : ''}>
        <Select
          label="Assignment type (preview)"
          value={assignmentType ?? ''}
          onChange={(v) => onAssignmentType(v || null)}
          options={atOpts}
        />
      </div>
      <div className={disabled ? 'opacity-60 pointer-events-none' : ''}>
        <Select
          label="Family status (preview)"
          value={familyStatus ?? ''}
          onChange={(v) => onFamilyStatus(v || null)}
          options={fsOpts}
        />
      </div>
      <div className="md:col-span-2 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-3 py-2.5 text-sm text-[#475569]">
        <p className="font-medium text-[#0b2b43] mb-1">How to use these selectors</p>
        <p className="text-xs leading-relaxed">
          This is a <strong>preview filter</strong> so you can see which rows apply to a given assignment and household
          context. You are still editing <strong>one</strong> company policy — not separate policies per selector.
          Per-employee or per-case exceptions may be added later; today, use the checkboxes on each row to limit who a
          benefit applies to (or leave them all unchecked to mean &quot;everyone&quot;).
        </p>
      </div>
    </div>
  );
};
