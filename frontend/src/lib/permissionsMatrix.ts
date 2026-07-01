import { ROUTE_DEFS, type RouteRole } from '../navigation/routes';

/**
 * Read-only "who can access what" matrix, derived purely from ROUTE_DEFS.
 *
 * IMPORTANT: ROUTE_DEFS[x].roles[] is *declared intent*, not the enforcement
 * boundary — no guard actually consumes it (the per-route guard components and the
 * backend `require_*` dependencies are the real boundary). This matrix surfaces the
 * declared access in one pane AND, via its snapshot test, turns that previously
 * un-enforced metadata into a drift-guarded artifact.
 */

export type MatrixRole = 'PUBLIC' | 'EMPLOYEE' | 'HR' | 'ADMIN';

export const MATRIX_ROLES: MatrixRole[] = ['PUBLIC', 'EMPLOYEE', 'HR', 'ADMIN'];

export interface MatrixRow {
  key: string;
  path: string;
  access: Record<MatrixRole, boolean>;
}

type RouteDefShape = Record<string, { path: string; roles: RouteRole[] }>;

export function buildPermissionsMatrix(defs: RouteDefShape = ROUTE_DEFS as RouteDefShape): MatrixRow[] {
  return Object.entries(defs)
    .map(([key, def]) => ({
      key,
      path: def.path,
      access: {
        PUBLIC: def.roles.includes('PUBLIC'),
        EMPLOYEE: def.roles.includes('EMPLOYEE'),
        HR: def.roles.includes('HR'),
        ADMIN: def.roles.includes('ADMIN'),
      },
    }))
    .sort((a, b) => a.path.localeCompare(b.path) || a.key.localeCompare(b.key));
}
