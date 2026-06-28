import type { CaseDraftDTO } from '../../../types';
import type { IntakeData } from './EmployeeIntakePage';

// Map the wizard's in-memory IntakeData onto the canonical CaseDraftDTO that the
// case record, HR views, and the plan/roadmap all read. Empty fields are left
// `undefined` so they drop out of the JSON and the backend deep-merge keeps any
// existing value (never overwriting good data with blanks). The submit handler
// previously patched only `{ services }`, so the rest of the intake never
// reached the case — this is the durable, full-payload write. Service selection
// is no longer collected in intake (it lives in the Service providers tab), so
// it is not written here.
//
// Pure (type-only imports) so it unit-tests without pulling in the app graph.
export function intakeToCaseDraft(data: IntakeData): Partial<CaseDraftDTO> {
  const partner = data.members.find((m) => m.kind === 'partner');
  const childMembers = data.members.filter((m) => m.kind === 'child');
  const hasDependents = data.members.some((m) => m.kind === 'partner' || m.kind === 'child');
  return {
    relocationBasics: {
      originCountry: data.origin_country || undefined,
      originCity: data.origin_city || undefined,
      destCountry: data.dest_country || undefined,
      destCity: data.dest_city || undefined,
      purpose: data.purpose || undefined,
      targetMoveDate: data.target_date || undefined,
      hasDependents,
    },
    employeeProfile: {
      fullName: data.full_name || undefined,
      nationality: data.nationality || undefined,
      passportCountry: data.passport_country || undefined,
      passportExpiry: data.passport_expiry || undefined,
      email: data.email || undefined,
    },
    familyMembers: {
      spouse: partner
        ? {
            fullName: partner.name || undefined,
            wantsToWork: partner.needs_work_permit?.toLowerCase() === 'yes' || undefined,
          }
        : undefined,
      children: childMembers.map((c) => ({
        dateOfBirth: c.dob || undefined,
        relationship: 'child',
      })),
    },
    assignmentContext: {
      jobTitle: data.job_title || undefined,
      contractType: data.contract_type || undefined,
      contractStartDate: data.contract_start || undefined,
      salaryBand: data.salary_band || undefined,
      workLocation: data.office_address || undefined,
      // AIQ-1349: STA/LTA/PERMANENT — backend bridges this onto
      // public.cases.assignment_type for duration-aware policy + roadmap.
      assignmentType: data.assignment_type || undefined,
    },
  };
}
