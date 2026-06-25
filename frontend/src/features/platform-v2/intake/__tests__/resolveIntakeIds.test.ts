import { describe, it, expect } from 'vitest';
import { resolveIntakeIds } from '../resolveIntakeIds';

const rows = [
  { assignment_id: 'asg-1', case_id: 'case-1' },
  { assignment_id: 'asg-2', case_id: 'case-2' },
  { assignment_id: 'asg-3', case_id: null },
];

describe('resolveIntakeIds', () => {
  it('resolves an assignment_id param (dashboard "Continue intake")', () => {
    // The bug: this used to return null and skip hydration.
    expect(resolveIntakeIds('asg-2', rows)).toEqual({ assignmentId: 'asg-2', caseId: 'case-2' });
  });

  it('resolves a case_id param (sidebar "Intake form")', () => {
    expect(resolveIntakeIds('case-1', rows)).toEqual({ assignmentId: 'asg-1', caseId: 'case-1' });
  });

  it('prefers an assignment_id match over a case_id match', () => {
    // If a param happens to equal one row's assignment_id and another's case_id,
    // the assignment_id match wins.
    const collide = [
      { assignment_id: 'X', case_id: 'other' },
      { assignment_id: 'asg-9', case_id: 'X' },
    ];
    expect(resolveIntakeIds('X', collide)).toEqual({ assignmentId: 'X', caseId: 'other' });
  });

  it('falls back caseId to the param for unknown ids (HR deep-link case UUID)', () => {
    expect(resolveIntakeIds('case-999', rows)).toEqual({ assignmentId: null, caseId: 'case-999' });
  });

  it('handles a row with a null case_id (caseId falls back to the param)', () => {
    expect(resolveIntakeIds('asg-3', rows)).toEqual({ assignmentId: 'asg-3', caseId: 'asg-3' });
  });

  it('returns nulls for an empty/undefined param (bare /employee/intake route)', () => {
    expect(resolveIntakeIds(undefined, rows)).toEqual({ assignmentId: null, caseId: null });
    expect(resolveIntakeIds('', rows)).toEqual({ assignmentId: null, caseId: null });
  });
});
