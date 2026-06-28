import { describe, it, expect } from 'vitest';
import {
  caseIdForAssignment,
  assignmentIdForScopeId,
  resolveScopedAssignmentId,
} from '../employeeAssignmentScope';
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

/**
 * AIQ-1334: employee case URLs are keyed by case_id. The services pages must
 * still resolve to the assignment_id their APIs use — assignmentIdForScopeId
 * accepts either id, and resolveScopedAssignmentId normalizes a case_id path
 * param so a case_id URL resolves even for multi-case employees (no false picker).
 */
describe('assignmentIdForScopeId', () => {
  it('maps a case_id to its assignment_id', () => {
    expect(assignmentIdForScopeId(rows, 'case-2')).toBe('assign-2');
  });
  it('returns the id unchanged when it is already an assignment_id', () => {
    expect(assignmentIdForScopeId(rows, 'assign-1')).toBe('assign-1');
  });
  it('falls back to the id itself when no row matches, and null for null', () => {
    expect(assignmentIdForScopeId(rows, 'unknown')).toBe('unknown');
    expect(assignmentIdForScopeId(rows, null)).toBeNull();
  });
});

describe('resolveScopedAssignmentId — case_id path param (AIQ-1334)', () => {
  it('resolves a case_id in the path to its assignment_id for a multi-case employee (no picker)', () => {
    const { effectiveId, needsPicker } = resolveScopedAssignmentId({
      linkedSummaries: rows,
      primaryAssignmentId: 'assign-1',
      queryAssignmentId: 'case-2', // a case_id in the URL
      preferredAssignmentId: null,
    });
    expect(effectiveId).toBe('assign-2');
    expect(needsPicker).toBe(false);
  });

  it('still resolves an assignment_id in the path directly', () => {
    const { effectiveId, needsPicker } = resolveScopedAssignmentId({
      linkedSummaries: rows,
      primaryAssignmentId: 'assign-1',
      queryAssignmentId: 'assign-2',
      preferredAssignmentId: null,
    });
    expect(effectiveId).toBe('assign-2');
    expect(needsPicker).toBe(false);
  });
});
