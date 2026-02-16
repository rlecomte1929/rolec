import React from 'react';
import type { AssignmentDetail } from '../types';

interface Props {
  assignment: AssignmentDetail | null;
}

const REQUIRED_PROFILE_FIELDS: { path: string; label: string }[] = [
  { path: 'primaryApplicant.fullName', label: 'Full name' },
  { path: 'primaryApplicant.nationality', label: 'Nationality' },
  { path: 'primaryApplicant.passport.expiryDate', label: 'Passport expiry' },
  { path: 'movePlan.origin', label: 'Origin' },
  { path: 'movePlan.destination', label: 'Destination' },
  { path: 'movePlan.targetArrivalDate', label: 'Target arrival date' },
  { path: 'primaryApplicant.employer.name', label: 'Employer name' },
  { path: 'primaryApplicant.employer.roleTitle', label: 'Job title' },
];

function getNestedValue(obj: any, path: string): any {
  return path.split('.').reduce((o, k) => o?.[k], obj);
}

export function getCaseMissingFields(assignment: AssignmentDetail | null): string[] {
  if (!assignment?.profile) return ['Entire profile'];
  const profile = assignment.profile;
  return REQUIRED_PROFILE_FIELDS.filter(
    (field) => !getNestedValue(profile, field.path),
  ).map((field) => field.label);
}

export const CaseIncompleteBanner: React.FC<Props> = ({ assignment }) => {
  const missing = getCaseMissingFields(assignment);
  if (missing.length === 0) return null;

  return (
    <div className="rounded-lg border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]">
      <div className="font-semibold">Employee case incomplete</div>
      <div className="text-xs mt-1">
        Profile missing: {missing.join(', ')}
      </div>
    </div>
  );
};
