import { describe, it, expect } from 'vitest';
import {
  adminPersonaFromPath,
  filterSectionsForAdminPath,
  adminPreviewLinks,
  ADMIN_NAV_SECTION,
  EMPLOYEE_NAV_SECTION,
  HR_NAV_SECTION,
} from '../adminNavScope';

const SECTIONS = [
  { label: ADMIN_NAV_SECTION, items: [{ id: 'coverage' }] },
  { label: EMPLOYEE_NAV_SECTION, items: [{ id: 'intake' }] },
  { label: HR_NAV_SECTION, items: [{ id: 'mobility-control' }] },
];

describe('adminNavScope', () => {
  it('maps /admin/coverage to the Admin persona', () => {
    expect(adminPersonaFromPath('/admin/coverage')).toBe('admin');
  });

  it('maps /hr/policy to HR', () => {
    expect(adminPersonaFromPath('/hr/policy')).toBe('hr');
  });

  it('maps employee routes to Employee', () => {
    expect(adminPersonaFromPath('/employee/welcome')).toBe('employee');
    expect(adminPersonaFromPath('/services')).toBe('employee');
    expect(adminPersonaFromPath('/dashboard')).toBe('employee');
  });

  it('hides HR Mobility command center on /admin/coverage', () => {
    const visible = filterSectionsForAdminPath(SECTIONS, '/admin/coverage', 'ADMIN');
    expect(visible.map((s) => s.label)).toEqual([ADMIN_NAV_SECTION]);
    expect(visible.some((s) => s.items.some((i) => i.id === 'mobility-control'))).toBe(false);
  });

  it('shows Policy section tree on /hr/policy, not Country requirements', () => {
    const visible = filterSectionsForAdminPath(SECTIONS, '/hr/policy', 'ADMIN');
    expect(visible.map((s) => s.label)).toEqual([HR_NAV_SECTION]);
    expect(visible.some((s) => s.label === ADMIN_NAV_SECTION)).toBe(false);
  });

  it('does not path-filter for HR-only sessions', () => {
    const visible = filterSectionsForAdminPath(SECTIONS, '/admin/coverage', 'HR');
    expect(visible).toHaveLength(3);
  });

  it('offers preview links on admin paths and back-to-admin elsewhere', () => {
    expect(adminPreviewLinks('admin').map((l) => l.label)).toEqual(['Preview HR', 'Preview Employee']);
    expect(adminPreviewLinks('hr')).toEqual([{ label: 'Back to Admin', to: '/admin' }]);
  });
});
