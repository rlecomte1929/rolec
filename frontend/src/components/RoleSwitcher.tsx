import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from './antigravity/Button';
import { authAPI } from '../api/client';
import {
  getStoredRoles,
  getActiveRole,
  setStoredRoles,
  setActiveRole,
  normalizeStoredRole,
} from '../utils/demo';
import { roleHomePath } from '../navigation/roleHome';

const ROLE_LABELS: Record<string, string> = {
  HR: 'HR',
  EMPLOYEE: 'Employee',
  ADMIN: 'Admin',
};

const labelFor = (role: string): string => ROLE_LABELS[normalizeStoredRole(role)] ?? role;

/**
 * AIQ-1357 — header role switcher for multi-role users. Rendered ONLY when the
 * user holds more than one role (single-role users see nothing). Selecting a
 * different role calls POST /api/auth/switch-role, updates the cached active
 * role, and navigates to that role's home (roleHomePath). The server is the
 * boundary — it 403s any role the user does not actually hold.
 *
 * AIQ-2295: segmented pills, not the heavy antigravity Select.
 */
export const RoleSwitcher: React.FC = () => {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const roles = getStoredRoles();
  const active = getActiveRole();

  if (roles.length <= 1) return null;

  const handleChange = async (next: string) => {
    const target = normalizeStoredRole(next);
    if (busy || target === active || !roles.includes(target)) return;
    setBusy(true);
    try {
      const res = await authAPI.switchRole(target);
      setStoredRoles(res.roles && res.roles.length ? res.roles : roles);
      const primary = res.primary_role || target;
      setActiveRole(primary);
      navigate(roleHomePath(primary));
    } catch {
      /* leave the active role unchanged on failure */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="group"
      aria-label="View as"
      className="inline-flex items-center gap-0.5 rounded-md bg-slate-100 p-0.5"
    >
      {roles.map((role) => {
        const selected = role === active;
        return (
          <Button
            key={role}
            unstyled
            type="button"
            disabled={busy}
            aria-pressed={selected}
            onClick={() => void handleChange(role)}
            className={`min-h-6 rounded px-2 text-xs font-medium transition-colors disabled:opacity-60 ${
              selected
                ? 'bg-white text-navy-800 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {labelFor(role)}
          </Button>
        );
      })}
    </div>
  );
};
