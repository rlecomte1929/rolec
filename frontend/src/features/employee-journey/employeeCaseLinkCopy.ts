/**
 * Single linking instruction for the unlinked employee dashboard (AIQ-2288).
 * Auto-link, code entry, and wait-for-HR live in this one paragraph.
 */
export const EMPLOYEE_CASE_LINK_INSTRUCTION =
  'If HR already set up a case for your verified email, it links when you sign in. If they sent you a code, enter it here. Otherwise wait for an email from HR.';

/** Real claim codes are assignment UUIDs (8-4-4-4-12 hex). Shared by helper + placeholder. */
export const EMPLOYEE_CASE_CODE_EXAMPLE = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
