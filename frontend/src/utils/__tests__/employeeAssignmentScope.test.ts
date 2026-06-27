import { describe, it, expect } from 'vitest';
import { caseIdForAssignment } from '../employeeAssignmentScope';
import type { EmployeeLinkedOverviewRow } from '../../types/employeeAssignmentOverview';

const rows = [
  { assignment_id: 'assign-1', case_id: 'case-1' },
  { assignment_id: 'assign-2', case_id: 'case-2' },
] as unknown as EmployeeLinkedOverviewRow[];

/**
 * AIQ-1320: services-state is case-scoped (/api/cases/{caseId}/services-state);
 * the services pages hold an assignment_id and must map it to the case_id, or
 * the GET/PUT 404 ("Case not found").
 */
describe('caseIdForAssignment', () => {
  it('maps a resolved assignment_id to its case_id', () => {
    expect(caseIdForAssignment(rows, 'assign-2')).toBe('case-2');
  });

  it('returns the id unchanged when it is already a case_id', () => {
    expect(caseIdForAssignment(rows, 'case-1')).toBe('case-1');
  });

  it('falls back to the id itself when no linked row matches', () => {
    expect(caseIdForAssignment(rows, 'unknown-id')).toBe('unknown-id');
    expect(caseIdForAssignment([], 'assign-1')).toBe('assign-1');
  });

  it('returns null for a null id', () => {
    expect(caseIdForAssignment(rows, null)).toBeNull();
  });
});
