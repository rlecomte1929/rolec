/** Persistent unlinked notice — info navy, not amber (AIQ-2293). */
export const employeeUnlinkedBannerClassName =
  'bg-navy-50 border-b border-navy-200 px-6 py-2 text-sm text-navy-800 shrink-0';

/** Action clause for the persistent unlinked-employee banner (AIQ-2287). */
export function employeeUnlinkedActionCopy(onDashboard: boolean): string {
  return onDashboard
    ? 'use Link case below to accept it'
    : 'open the Dashboard to accept it';
}
