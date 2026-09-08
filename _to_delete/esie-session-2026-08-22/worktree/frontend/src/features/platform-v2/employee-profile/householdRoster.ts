/**
 * Household roster — ask-once helper.
 *
 * The Rich Profile page must NOT re-ask for household names/DOBs: the employee
 * already entered them in the intake wizard (Step 3 `familyMembers`). This maps
 * that wizard draft into the read-only roster the page renders enrichment
 * sections against. Pure logic, no React — unit-tested in householdRoster.test.ts.
 */
import type { FamilyMembersDTO } from '../../../types';

export interface HouseholdMember {
  id: string;
  kind: 'self' | 'partner' | 'child' | 'pet';
  name?: string;
  dob?: string;
  pet_type?: string;
  breed?: string;
}

/** Marital statuses that imply a partner is part of the household. */
export const PARTNERED_STATUSES = ['Married', 'Partnership'];

/** Build the read-only household roster from the wizard's familyMembers draft. */
export function draftToMembers(fm: FamilyMembersDTO | undefined, selfName?: string): HouseholdMember[] {
  const out: HouseholdMember[] = [{ id: 'self', kind: 'self', name: selfName || 'You' }];
  const spouse = fm?.spouse;
  const partnered = !!spouse?.fullName || PARTNERED_STATUSES.includes(fm?.maritalStatus ?? '');
  if (partnered) {
    out.push({ id: 'partner', kind: 'partner', name: spouse?.fullName, dob: spouse?.dateOfBirth });
  }
  (fm?.children ?? []).forEach((c, i) => {
    out.push({ id: `c${i}`, kind: 'child', name: c.fullName, dob: c.dateOfBirth });
  });
  return out;
}
