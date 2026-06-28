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
    <Select
      value={active}
      onChange={(v) => void handleChange(v)}
      options={roles.map((r) => ({ value: r, label: `View as ${labelFor(r)}` }))}
    />
  );
};
