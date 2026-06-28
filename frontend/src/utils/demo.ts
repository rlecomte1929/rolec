export const getAuthItem = (key: string) => localStorage.getItem(key);

/** Normalize role from API/storage so ADMIN/HR/EMPLOYEE comparisons stay reliable. */
export const normalizeStoredRole = (raw: string | null | undefined): string =>
  (raw ?? '').trim().toUpperCase();

export const setAuthItem = (key: string, value: string) => {
  localStorage.setItem(key, value);
};

export const clearAuthItems = () => {
  Object.keys(localStorage)
    .filter((key) => key.startsWith('relopass_'))
    .forEach((key) => localStorage.removeItem(key));
};

// ── Multi-role (AIQ-1363) ────────────────────────────────────────────────────
const ROLES_KEY = 'relopass_roles';
const ACTIVE_ROLE_KEY = 'relopass_active_role';

/** Persist all roles the user holds (from the login/switch response). */
export const setStoredRoles = (roles: Array<string | null | undefined>) => {
  const norm = roles.map(normalizeStoredRole).filter(Boolean);
  setAuthItem(ROLES_KEY, JSON.stringify(norm));
};

/** All roles the user holds (membership). Falls back to the single
 *  `relopass_role` for legacy sessions that predate roles[]. */
export const getStoredRoles = (): string[] => {
  const raw = getAuthItem(ROLES_KEY);
  if (raw) {
    try {
      const arr: unknown = JSON.parse(raw);
      if (Array.isArray(arr) && arr.length) {
        return arr.map((r) => normalizeStoredRole(String(r))).filter(Boolean);
      }
    } catch {
      /* fall through to single-role */
    }
  }
  const single = normalizeStoredRole(getAuthItem('relopass_role'));
  return single ? [single] : [];
};

/** The active/primary role — drives default home + which portal is shown. */
export const getActiveRole = (): string =>
  normalizeStoredRole(getAuthItem(ACTIVE_ROLE_KEY)) || normalizeStoredRole(getAuthItem('relopass_role'));

/** Set the active role (and mirror to `relopass_role` for legacy reads). */
export const setActiveRole = (role: string) => {
  const norm = normalizeStoredRole(role);
  setAuthItem(ACTIVE_ROLE_KEY, norm);
  setAuthItem('relopass_role', norm);
};
