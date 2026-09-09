export const ADMIN_NAV_SECTION = 'Admin · ReloPass';
export const EMPLOYEE_NAV_SECTION = 'Employee';
export const HR_NAV_SECTION = 'HR Operations';

export type AdminNavPersona = 'admin' | 'hr' | 'employee';
export type SidebarRole = 'EMPLOYEE' | 'HR' | 'ADMIN';

/** Which persona tree an Admin should see for the current URL. Inbox stays pinned separately. */
export function adminPersonaFromPath(pathname: string): AdminNavPersona {
  if (pathname === '/hr' || pathname.startsWith('/hr/')) return 'hr';
  if (
    pathname === '/employee' ||
    pathname.startsWith('/employee/') ||
    pathname === '/journey' ||
    pathname.startsWith('/journey/') ||
    pathname === '/dashboard' ||
    pathname.startsWith('/dashboard/') ||
    pathname === '/services' ||
    pathname.startsWith('/services/')
  ) {
    return 'employee';
  }
  return 'admin';
}

export function sectionMatchesAdminPersona(sectionLabel: string, persona: AdminNavPersona): boolean {
  if (persona === 'admin') return sectionLabel === ADMIN_NAV_SECTION;
  if (persona === 'hr') return sectionLabel === HR_NAV_SECTION;
  return sectionLabel === EMPLOYEE_NAV_SECTION;
}

export function filterSectionsForAdminPath<T extends { label: string }>(
  sections: T[],
  pathname: string,
  role: SidebarRole,
): T[] {
  if (role !== 'ADMIN') return sections;
  const persona = adminPersonaFromPath(pathname);
  return sections.filter((s) => sectionMatchesAdminPersona(s.label, persona));
}

export function adminPreviewLinks(persona: AdminNavPersona): { label: string; to: string }[] {
  if (persona === 'admin') {
    return [
      { label: 'Preview HR', to: '/hr/command-center' },
      { label: 'Preview Employee', to: '/employee/welcome' },
    ];
  }
  return [{ label: 'Back to Admin', to: '/admin' }];
}
