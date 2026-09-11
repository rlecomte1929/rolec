import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Select } from './antigravity/Select';
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
 */
export const RoleSwitcher: React.FC = () => {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const roles = getStoredRoles();
  const active = getActiveRole();

  if (roles.length <= 1) return null;

  const handleChange = async (next: string) => {
    const target = normalizeStoredRole(next);
    if (busy || target === active || !roles.includes(target)) return;
    setBusy(true);
    setSwitchError(null);
    try {
      const res = await authAPI.switchRole(target);
      setStoredRoles(res.roles && res.roles.length ? res.roles : roles);
      // Honor the role the user picked. primary_role on the response is the
      // server's default home, not "what I just clicked" — using it here left
      // the combobox on Employee after choosing View as HR.
      setActiveRole(target);
      navigate(roleHomePath(target));
    } catch {
      setSwitchError('Could not switch role. Try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col items-end">
      <Select
        value={active}
        onChange={(v) => void handleChange(v)}
        options={roles.map((r) => ({ value: r, label: `View as ${labelFor(r)}` }))}
      />
      {switchError ? (
        <p className="mt-1 max-w-[12rem] text-right text-[11px] text-rose-700" role="alert">
          {switchError}
        </p>
      ) : null}
    </div>
  );
};
