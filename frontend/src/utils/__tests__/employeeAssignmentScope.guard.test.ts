import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

/**
 * AIQ-1704 B3 guard: the two boundary resolvers must FAIL CLOSED on a miss.
 *
 * caseIdForAssignment / assignmentIdForScopeId used to return the raw input id when
 * no linked row matched — on a miss that id is often the ASSIGNMENT id, which a
 * case-keyed endpoint reads as the wrong case (the silent-empty class). B1 changed
 * them to return `null`. This source-scan stops a future edit from silently
 * reintroducing the `?? id` fallback (which the behavioural tests might not catch on
 * an untested path). Callers that still want a raw-id last resort do so explicitly.
 */
// vitest runs with cwd = frontend/, so resolve the source relative to that.
const SRC = readFileSync(
  resolve(process.cwd(), 'src/utils/employeeAssignmentScope.ts'),
  'utf8',
);

function bodyOf(fnName: string): string {
  const start = SRC.indexOf(`export function ${fnName}(`);
  expect(start, `${fnName} not found`).toBeGreaterThan(-1);
  const end = SRC.indexOf('\n}', start);
  return SRC.slice(start, end);
}

describe('employeeAssignmentScope resolvers fail closed (AIQ-1704)', () => {
  it('caseIdForAssignment returns null on a miss, never the raw id', () => {
    const body = bodyOf('caseIdForAssignment');
    expect(body).toContain('?? null');
    expect(body).not.toMatch(/\?\?\s*id\b/);
  });

  it('assignmentIdForScopeId returns null on a miss, never the raw id', () => {
    const body = bodyOf('assignmentIdForScopeId');
    expect(body).toContain('?? null');
    expect(body).not.toMatch(/\?\?\s*id\b/);
  });
});
