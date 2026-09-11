/** Action clause for the persistent unlinked-employee banner (AIQ-2287). */
export function employeeUnlinkedActionCopy(onDashboard: boolean): string {
  return onDashboard
    ? 'use Link case below to accept it'
    : 'open the Dashboard to accept it';
}
