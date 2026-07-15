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

  const assignmentId = notification.assignment_id || notification.case_id;
  if (!assignmentId) return '/';

  if (role === 'EMPLOYEE') {
    return `/employee/case/${assignmentId}/summary`;
  }
  return `/hr/employee-dashboard?caseId=${assignmentId}`;
}
