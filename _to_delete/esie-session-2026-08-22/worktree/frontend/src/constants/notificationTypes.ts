/**
 * Notification types - stable enum-like constants for 6A/6B/6C.
 * Keep consistent for future email templates and preferences.
 */
export const NOTIFICATION_TYPES = {
  HR_FEEDBACK_POSTED: 'HR_FEEDBACK_POSTED',
  EMPLOYEE_SAVED: 'EMPLOYEE_SAVED',
  CASE_STATUS_CHANGED: 'CASE_STATUS_CHANGED',
  INTAKE_SUBMITTED: 'INTAKE_SUBMITTED',
  // [AIQ-1376] fired to the employee when HR assigns them a relocation case.
  ASSIGNMENT_CREATED: 'ASSIGNMENT_CREATED',
  // [AIQ-1547] fired to the admin (in-app, no email) when a test-drive tester completes.
  TEST_DRIVE_COMPLETED: 'TEST_DRIVE_COMPLETED',
  // [AIQ-1570] fired to the assigned HR when an employee files an over-cap exception
  // request from the estimate page. Must match the backend string in
  // backend/app/routers/exception_requests.py.
  POLICY_EXCEPTION_REQUESTED: 'POLICY_EXCEPTION_REQUESTED',
  // fired to the EMPLOYEE when HR approves/rejects their exception. The other half of the
  // loop — before this, HR decided and nobody told the person who asked.
  POLICY_EXCEPTION_DECIDED: 'POLICY_EXCEPTION_DECIDED',
} as const;

export type NotificationType = (typeof NOTIFICATION_TYPES)[keyof typeof NOTIFICATION_TYPES];

export interface Notification {
  id: string;
  created_at: string;
  assignment_id: string | null;
  case_id: string | null;
  type: string;
  title: string;
  body: string | null;
  metadata: Record<string, unknown>;
  read_at: string | null;
}

/**
 * Map notification to target route for the current role.
 * 6C: extend metadata for email deep links.
 */
export function getNotificationTarget(
  role: 'HR' | 'EMPLOYEE' | 'ADMIN',
  notification: Pick<Notification, 'assignment_id' | 'case_id' | 'type'>
): string {
  // [AIQ-1547] test-drive completion notifications deep-link to the campaign dashboard.
  if (notification.type === NOTIFICATION_TYPES.TEST_DRIVE_COMPLETED) {
    return '/admin/test-drive';
  }

  // [AIQ-1570] An over-cap request is actioned in the exceptions inbox — the default
  // employee-dashboard target below has no approve/reject flow.
  if (notification.type === NOTIFICATION_TYPES.POLICY_EXCEPTION_REQUESTED) {
    return '/hr/exceptions';
  }

  // The decision lands on the employee's Benefit comparison — the page they asked from, and
  // the only one that shows the request's status. The case-summary default below shows
  // nothing about exceptions.
  if (notification.type === NOTIFICATION_TYPES.POLICY_EXCEPTION_DECIDED) {
    return '/employee/benefits';
  }

  const assignmentId = notification.assignment_id || notification.case_id;
  if (!assignmentId) return '/';

  if (role === 'EMPLOYEE') {
    return `/employee/case/${assignmentId}/summary`;
  }
  return `/hr/employee-dashboard?caseId=${assignmentId}`;
}
