import { describe, it, expect } from 'vitest';
import { EMPLOYEE_CASE_LINK_INSTRUCTION } from './employeeCaseLinkCopy';

describe('EMPLOYEE_CASE_LINK_INSTRUCTION (AIQ-2288)', () => {
  it('covers auto-link, code entry, and wait-for-HR in one sentence', () => {
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).toMatch(/links when you sign in/i);
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).toMatch(/code/i);
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).toMatch(/wait for an email/i);
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).not.toMatch(/no code needed/i);
    expect(EMPLOYEE_CASE_LINK_INSTRUCTION).not.toMatch(/ask your hr team to create/i);
  });
});
