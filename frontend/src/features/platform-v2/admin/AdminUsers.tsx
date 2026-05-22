/**
 * AdminUsers.tsx — T21  /admin/users
 * ─────────────────────────────────────────────────────────────────────────────
 * User management for admin+ roles.
 * Filter chips · search · user table · inline role edit · invite slide-over
 */

import { useState, useMemo } from 'react';
import { Pill, FilterChips, Avatar, DateFormatter, EmptyState, LoadingSpinner } from '../shared';
import type { UserRole, PlanTier } from '../../../types/relopass-api-contracts';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AdminUserRow {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  company_name: string;
  plan_tier: PlanTier;
  last_login: string | null;
  status: 'active' | 'suspended';
  avatar_url?: string | null;
}

export interface AdminUsersProps {
  users?: AdminUserRow[];
  companies?: { id: string; name: string }[];
  loading?: boolean;
  onEditRole?: (userId: string, role: UserRole) => Promise<void>;
  onToggleStatus?: (userId: string, next: 'active' | 'suspended') => Promise<void>;
  onResetPassword?: (userId: string) => void;
  onInviteUser?: (data: InviteUserPayload) => Promise<void>;
}

export interface InviteUserPayload {
  email: string;
  role: UserRole;
  company_id: string;
}

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_USERS: AdminUserRow[] = [
  { id: 'u1', full_name: 'Sarah Chen',    email: 'sarah@acme.com',    role: 'admin',    company_name: 'Acme Corp',  plan_tier: 'admin', last_login: '2026-05-20T08:00:00Z', status: 'active' },
  { id: 'u2', full_name: 'Marc Bouchard', email: 'marc@acme.com',     role: 'employee', company_name: 'Acme Corp',  plan_tier: 'admin', last_login: '2026-05-19T14:00:00Z', status: 'active' },
  { id: 'u3', full_name: 'Julia Hoffmann',email: 'julia@globex.com',  role: 'hr',       company_name: 'Globex Inc', plan_tier: 'hr',    last_login: '2026-05-18T09:00:00Z', status: 'active' },
  { id: 'u4', full_name: 'Tom Fischer',   email: 'tom@initech.com',   role: 'employee', company_name: 'Initech',    plan_tier: 'basic', last_login: '2026-04-10T11:00:00Z', status: 'suspended' },
  { id: 'u5', full_name: 'Ana Ribeiro',   email: 'ana@umbrella.com',  role: 'hr',       company_name: 'Umbrella Ltd',plan_tier:'hr',    last_login: '2026-05-17T16:00:00Z', status: 'active' },
];

const MOCK_COMPANIES = [
  { id: 'c1', name: 'Acme Corp' },
  { id: 'c2', name: 'Globex Inc' },
  { id: 'c3', name: 'Initech' },
  { id: 'c4', name: 'Umbrella Ltd' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const ROLE_VARIANT: Record<UserRole, 'success' | 'warning' | 'info' | 'muted'> = {
  admin:          'success',
  hr:             'warning',
  employee:       'info',
  vendor_contact: 'muted',
};

const ROLE_LABELS: Record<UserRole, string> = {
  admin:          'Admin',
  hr:             'HR',
  employee:       'Employee',
  vendor_contact: 'Vendor',
};

const TIER_VARIANT: Record<PlanTier, 'info' | 'warning' | 'success'> = {
  basic: 'info',
  hr:    'warning',
  admin: 'success',
};

type RoleFilter = 'all' | UserRole;

const ROLE_FILTERS = [
  { id: 'all',      label: 'All' },
  { id: 'admin',    label: 'Admin' },
  { id: 'hr',       label: 'HR' },
  { id: 'employee', label: 'Employee' },
];

// ── Invite slide-over ─────────────────────────────────────────────────────────

function InviteUserSlideOver({
  companies,
  onClose,
  onSubmit,
}: {
  companies: { id: string; name: string }[];
  onClose: () => void;
  onSubmit: (data: InviteUserPayload) => Promise<void>;
}) {
  const [form, setForm] = useState<InviteUserPayload>({ email: '', role: 'employee', company_id: companies[0]?.id ?? '' });
  const [saving, setSaving] = useState(false);

  function field<K extends keyof InviteUserPayload>(k: K, v: InviteUserPayload[K]) {
    setForm(f => ({ ...f, [k]: v }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try { await onSubmit(form); onClose(); } finally { setSaving(false); }
  }

  return (
    <>
      <div aria-hidden="true" onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'var(--overlay)', zIndex: 'var(--z-overlay)' as never }} />
      <aside
        role="dialog" aria-modal="true" aria-label="Invite user"
        style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 'var(--drawer-w)', background: 'var(--surface)', borderLeft: '1px solid var(--border)', boxShadow: 'var(--shadow-4)', zIndex: 'var(--z-panel)' as never, display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>Invite user</h2>
          <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>
            Email address
            <input
              type="email" required placeholder="user@company.com"
              value={form.email} onChange={e => field('email', e.target.value)}
              style={{ height: 'var(--input-h)', padding: '0 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '14px' }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>
            Role
            <select
              value={form.role} onChange={e => field('role', e.target.value as UserRole)}
              style={{ height: 'var(--input-h)', padding: '0 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '14px' }}
            >
              <option value="employee">Employee</option>
              <option value="hr">HR</option>
              <option value="admin">Admin</option>
              <option value="vendor_contact">Vendor contact</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>
            Company
            <select
              value={form.company_id} onChange={e => field('company_id', e.target.value)}
              style={{ height: 'var(--input-h)', padding: '0 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '14px' }}
            >
              {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>

          <div style={{ marginTop: 'auto', paddingTop: '16px', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button type="button" onClick={onClose} style={{ padding: '8px 16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '14px', cursor: 'pointer' }}>
              Cancel
            </button>
            <button
              type="submit" disabled={saving}
              style={{ padding: '8px 20px', borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}
            >
              {saving ? 'Sending…' : 'Send invite'}
            </button>
          </div>
        </form>
      </aside>
    </>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function AdminUsers({
  users = MOCK_USERS,
  companies = MOCK_COMPANIES,
  loading = false,
  onEditRole,
  onToggleStatus,
  onResetPassword,
  onInviteUser,
}: AdminUsersProps) {
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');
  const [search, setSearch] = useState('');
  const [slideOver, setSlideOver] = useState(false);
  const [editingRole, setEditingRole] = useState<Record<string, UserRole>>({});
  const [savingRole, setSavingRole] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let rows = users;
    if (roleFilter !== 'all') rows = rows.filter(u => u.role === roleFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(u =>
        u.full_name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        u.company_name.toLowerCase().includes(q)
      );
    }
    return rows;
  }, [users, roleFilter, search]);

  const counts: Record<RoleFilter, number> = {
    all:            users.length,
    admin:          users.filter(u => u.role === 'admin').length,
    hr:             users.filter(u => u.role === 'hr').length,
    employee:       users.filter(u => u.role === 'employee').length,
    vendor_contact: users.filter(u => u.role === 'vendor_contact').length,
  };

  const chipsWithCounts = ROLE_FILTERS.map(c => ({ ...c, count: counts[c.id as RoleFilter] }));

  async function handleRoleChange(userId: string, role: UserRole) {
    setEditingRole(r => ({ ...r, [userId]: role }));
    setSavingRole(userId);
    try { await onEditRole?.(userId, role); } finally { setSavingRole(null); }
  }

  async function handleInvite(data: InviteUserPayload) {
    await onInviteUser?.(data);
  }

  return (
    <div style={{ padding: 'var(--page-py) var(--page-px)', maxWidth: 'var(--content-max-w)', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-3xl)', fontWeight: 700, color: 'var(--text)' }}>Users</h1>
          <p style={{ margin: '4px 0 0', fontSize: '14px', color: 'var(--text-muted)' }}>Manage platform users across all companies</p>
        </div>
        <button
          onClick={() => setSlideOver(true)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '0 18px', height: 'var(--btn-h-md)', borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          Invite user
        </button>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 220px', maxWidth: '320px' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="search"
            placeholder="Search users…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%', height: 'var(--input-h)', padding: '0 12px 0 32px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '13px' }}
          />
        </div>
        <FilterChips chips={chipsWithCounts} selected={roleFilter} onSelect={id => setRoleFilter(id as RoleFilter)} />
      </div>

      {/* Table */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        {loading ? (
          <LoadingSpinner centered />
        ) : filtered.length === 0 ? (
          <EmptyState icon="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" title="No users found" description="Try adjusting your search or filters." />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)' }}>
                  {['Name', 'Email', 'Role', 'Company', 'Plan', 'Last login', 'Status', 'Actions'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(user => {
                  const currentRole = editingRole[user.id] ?? user.role;
                  return (
                    <tr
                      key={user.id}
                      style={{ borderBottom: '1px solid var(--border)', transition: 'background var(--transition-fast)' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-hover)')}
                      onMouseLeave={e => (e.currentTarget.style.background = '')}
                    >
                      {/* Name + avatar */}
                      <td style={{ padding: '12px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Avatar name={user.full_name} src={user.avatar_url ?? undefined} size={30} />
                          <span style={{ fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap' }}>{user.full_name}</span>
                        </div>
                      </td>

                      {/* Email */}
                      <td style={{ padding: '12px 14px', color: 'var(--text-secondary)', fontSize: '12px' }}>{user.email}</td>

                      {/* Role — inline select */}
                      <td style={{ padding: '12px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <select
                            value={currentRole}
                            disabled={savingRole === user.id}
                            onChange={e => handleRoleChange(user.id, e.target.value as UserRole)}
                            aria-label={`Role for ${user.full_name}`}
                            style={{
                              height: '26px', padding: '0 6px', fontSize: '12px',
                              borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
                              background: 'var(--surface)', color: 'var(--text)',
                              cursor: savingRole === user.id ? 'not-allowed' : 'pointer',
                              opacity: savingRole === user.id ? 0.6 : 1,
                            }}
                          >
                            <option value="employee">Employee</option>
                            <option value="hr">HR</option>
                            <option value="admin">Admin</option>
                            <option value="vendor_contact">Vendor</option>
                          </select>
                          <Pill variant={ROLE_VARIANT[currentRole]} size="sm">{ROLE_LABELS[currentRole]}</Pill>
                        </div>
                      </td>

                      {/* Company */}
                      <td style={{ padding: '12px 14px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{user.company_name}</td>

                      {/* Plan tier */}
                      <td style={{ padding: '12px 14px' }}>
                        <Pill variant={TIER_VARIANT[user.plan_tier]} size="sm">{user.plan_tier}</Pill>
                      </td>

                      {/* Last login */}
                      <td style={{ padding: '12px 14px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {user.last_login
                          ? <DateFormatter date={user.last_login} format="relative" />
                          : <span style={{ color: 'var(--text-disabled)' }}>Never</span>}
                      </td>

                      {/* Status */}
                      <td style={{ padding: '12px 14px' }}>
                        <Pill variant={user.status === 'active' ? 'success' : 'danger'} size="sm" dot>{user.status}</Pill>
                      </td>

                      {/* Row actions */}
                      <td style={{ padding: '12px 14px' }}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'nowrap' }}>
                          <button
                            onClick={() => onToggleStatus?.(user.id, user.status === 'active' ? 'suspended' : 'active')}
                            style={{
                              padding: '4px 8px', fontSize: '11px', fontWeight: 600, borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                              border: `1px solid ${user.status === 'active' ? 'var(--pill-danger-border)' : 'var(--pill-success-border)'}`,
                              background: user.status === 'active' ? 'var(--pill-danger-bg)' : 'var(--pill-success-bg)',
                              color: user.status === 'active' ? 'var(--pill-danger-text)' : 'var(--pill-success-text)',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {user.status === 'active' ? 'Suspend' : 'Activate'}
                          </button>
                          <button
                            onClick={() => {
                              onResetPassword?.(user.id);
                              window.dispatchEvent(new CustomEvent('rp:reset-password', { detail: { userId: user.id, email: user.email } }));
                            }}
                            style={{ padding: '4px 8px', fontSize: '11px', fontWeight: 600, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', cursor: 'pointer', whiteSpace: 'nowrap' }}
                          >
                            Reset pwd
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {slideOver && (
        <InviteUserSlideOver
          companies={companies}
          onClose={() => setSlideOver(false)}
          onSubmit={handleInvite}
        />
      )}
    </div>
  );
}

export default AdminUsers;
