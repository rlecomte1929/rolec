/**
 * Inbox persona follows the route, not localStorage `relopass_role`.
 * /hr/messages is always the HR inbox; /messages (and /messages-v2) is always
 * the employee inbox. Fixes AIQ-2362 / AIQ-2363.
 */

export function isHrInboxPath(pathname: string): boolean {
  return pathname === '/hr/messages' || pathname.startsWith('/hr/messages/');
}

export function isEmployeeInboxPath(pathname: string): boolean {
  return (
    pathname === '/messages' ||
    pathname.startsWith('/messages/') ||
    pathname === '/messages-v2'
  );
}

export function inboxPathForRole(role: string): string {
  return role.trim().toUpperCase() === 'EMPLOYEE' ? '/messages' : '/hr/messages';
}

/** When already on an inbox, keep the counterpart inbox after a role switch. */
export function roleSwitchInboxPath(targetRole: string, pathname: string): string | null {
  if (!isHrInboxPath(pathname) && !isEmployeeInboxPath(pathname)) return null;
  return inboxPathForRole(targetRole);
}
