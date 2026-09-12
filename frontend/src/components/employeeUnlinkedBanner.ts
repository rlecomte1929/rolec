/** Persistent unlinked notice — info navy, not amber (AIQ-2293). */
export const employeeUnlinkedBannerClassName =
  'bg-navy-50 border-b border-navy-200 px-6 py-2 text-sm text-navy-800 shrink-0';

/** Session-scoped dismiss key for the unlinked-case banner (AIQ-2356). */
export const UNLINKED_BANNER_DISMISS_KEY = 'relopass_unlinked_banner_dismissed';

/**
 * Pages that already render {@link NoCaseLinkedEmptyState} (or the Services
 * equivalent). The global banner would stack on the same message (AIQ-2356).
 */
export function employeeUnlinkedBannerHasPageEmptyState(pathname: string): boolean {
  const path = (pathname.split('?')[0] ?? pathname).replace(/\/$/, '') || '/';
  if (path === '/employee/dashboard' || path === '/employee') return true;
  if (path.startsWith('/employee/case/')) return true;
  if (path.startsWith('/services')) return true;
  const prefixes = [
    '/employee/tasks',
    '/employee/benefits',
    '/employee/immigration',
    '/employee/immigration-assistant',
  ];
  return prefixes.some((p) => path === p || path.startsWith(`${p}/`));
}

/** Action clause for the persistent unlinked-employee banner (AIQ-2287). */
export function employeeUnlinkedActionCopy(onDashboard: boolean): string {
  return onDashboard
    ? 'use Link case below to accept it'
    : 'open the Dashboard to accept it';
}
