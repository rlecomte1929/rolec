import { describe, it, expect } from 'vitest';
import { ROUTE_DEFS } from '../navigation/routes';
import { buildPermissionsMatrix, MATRIX_ROLES } from './permissionsMatrix';

describe('buildPermissionsMatrix', () => {
  it('emits one row per route, faithful to ROUTE_DEFS.roles[] (drift guard)', () => {
    const rows = buildPermissionsMatrix();
    expect(rows).toHaveLength(Object.keys(ROUTE_DEFS).length);
    // Every row's access booleans must equal the source roles[].includes — this is
    // the guard: if a route's roles[] changes, this assertion forces the matrix to follow.
    for (const row of rows) {
      const src = (ROUTE_DEFS as Record<string, { roles: string[] }>)[row.key];
      expect(src).toBeDefined();
      for (const role of MATRIX_ROLES) {
        expect(row.access[role]).toBe(src.roles.includes(role));
      }
    }
  });

  it('classifies representative routes correctly', () => {
    const byKey = Object.fromEntries(buildPermissionsMatrix().map((r) => [r.key, r.access]));
    // landing is PUBLIC-only
    expect(byKey.landing).toEqual({ PUBLIC: true, EMPLOYEE: false, HR: false, ADMIN: false });
    // an admin route is ADMIN-only
    expect(byKey.adminConsole.ADMIN).toBe(true);
    expect(byKey.adminConsole.EMPLOYEE).toBe(false);
  });

  it('is sorted by path for stable rendering', () => {
    const paths = buildPermissionsMatrix().map((r) => r.path);
    const sorted = [...paths].sort((a, b) => a.localeCompare(b));
    expect(paths).toEqual(sorted);
  });
});
