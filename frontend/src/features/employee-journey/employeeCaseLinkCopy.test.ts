import { describe, it, expect } from 'vitest';
import {
  assignmentStatusPillCopy,
  EMPLOYEE_CASE_CODE_EXAMPLE,
  EMPLOYEE_CASE_LINK_INSTRUCTION,
} from './employeeCaseLinkCopy';

describe('EMPLOYEE_CASE_LINK_INSTRUCTION (AIQ-2288)', () => {
  it('covers auto-link, code entry, and wait-for-HR in one sentence', () => {
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).toMatch(/links when you sign in/i);
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).toMatch(/code/i);
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).toMatch(/wait for an email/i);
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).not.toMatch(/no code needed/i);
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).not.toMatch(/ask your hr team to create/i);
  });
});

describe('EMPLOYEE_CASE_CODE_EXAMPLE (AIQ-2289)', () => {
  it('is a UUID-shaped example, not a short abc-123 slug', () => {
    expect(EMPLOYEE_CASE_CODE_EXAMPLE).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(EMPLOYEE_CASE_CODE_EXAMPLE).not.toMatch(/abc-123/i);
  });
});

describe('assignmentStatusPillCopy (AIQ-2291)', () => {
  it('keeps every pill under 20 characters with no how-to', () => {
    for (const kind of ['linked', 'pending', 'waiting', 'unlinked'] as const) {
      const label = assignmentStatusPillCopy(kind);
      expect(label.length).toBeLessThanOrEqual(20);
      expect(label).not.toMatch(/claim|email|below|use /i);
    }
    expect(assignmentStatusPillCopy('unlinked')).toBe('Not linked');
  });
});
