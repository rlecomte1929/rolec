import { describe, it, expect } from 'vitest';
import {
  caseIdForAssignment,
  ownedEmployeeCaseId,
  persistableCaseId,
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

  it('returns null when no linked row matches (fail closed, AIQ-1704)', () => {
    expect(caseIdForAssignment(rows, 'unknown-id')).toBeNull();
    expect(caseIdForAssignment([], 'assign-1')).toBeNull();
  });

  it('returns null for a null id', () => {
    expect(caseIdForAssignment(rows, null)).toBeNull();
  });
});

describe('ownedEmployeeCaseId (AIQ-2358 / AIQ-2359)', () => {
  it('ignores a stale candidate when the employee has no linked case', () => {
    expect(ownedEmployeeCaseId([], ['053c93bb-6ba4-4a7e-a26d-bc05dcfe3abe'])).toBeNull();
  });

  it('prefers the first owned candidate over later ones', () => {
    expect(ownedEmployeeCaseId(rows, ['unknown', 'assign-2', 'case-1'])).toBe('case-2');
  });

  it('falls back to the primary linked case when candidates are empty', () => {
    expect(ownedEmployeeCaseId(rows, [null, undefined])).toBe('case-1');
  });
});

/**
 * AIQ-1691: `caseIdForAssignment` falls back to the raw id on a miss. While the
 * linked summaries are still loading (empty), that raw id is the ASSIGNMENT id,
 * and persisting services-state against it 404s — the exact intermittent bug
 * where early "Add to package" saves are dropped. `persistableCaseId` returns
 * null until the summaries have loaded so the caller never persists a wrong id.
 */
describe('persistableCaseId', () => {
  it('returns null while summaries are still loading (never the raw assignment id)', () => {
    // AIQ-1704: caseIdForAssignment now returns null on a miss; the mid-load guard
    // returns null regardless (never guesses while summaries are still loading).
    expect(caseIdForAssignment([], 'assign-1')).toBeNull();
    expect(persistableCaseId([], 'assign-1', false)).toBeNull();
    // Even with summaries present, `loaded=false` means don't guess yet.
    expect(persistableCaseId(rows, 'assign-1', false)).toBeNull();
  });

  it('resolves to the case_id once summaries have loaded', () => {
    expect(persistableCaseId(rows, 'assign-2', true)).toBe('case-2');
    expect(persistableCaseId(rows, 'case-1', true)).toBe('case-1');
  });

  it('falls back to the id after load only for a genuine legacy no-match', () => {
    // Loaded + no linked row: a case_id URL still persists correctly against itself.
    expect(persistableCaseId(rows, 'case-legacy', true)).toBe('case-legacy');
  });

  it('returns null for a null id regardless of load state', () => {
    expect(persistableCaseId(rows, null, true)).toBeNull();
    expect(persistableCaseId(rows, null, false)).toBeNull();
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
  it('returns null when no row matches, and null for null (fail closed, AIQ-1704)', () => {
    expect(assignmentIdForScopeId(rows, 'unknown')).toBeNull();
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
