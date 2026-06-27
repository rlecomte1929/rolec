/**
 * AdminDashboard.tsx — T18 / S9  /admin
 * ─────────────────────────────────────────────────────────────────────────────
 * Platform-wide metrics for admin+ roles.
 * Stat cards · companies table · new-company slide-over · event feed
 */

import type * as React from 'react';
import { useState } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import {
  StatCard,
  Pill,
  Avatar,
  DateFormatter,
  EmptyState,
  LoadingSpinner,
} from '../shared';
import type { PlanTier } from '../../../types/relopass-api-contracts';

// ── Local types ───────────────────────────────────────────────────────────────

export interface AdminCompanyRow {
  id: string;
  name: string;
  slug: string;
  plan_tier: PlanTier;
  case_count: number;
  user_count: number;
  created_at: string;
  status: 'active' | 'suspended';
}

export interface PlatformEvent {
  id: string;
  type: 'company_created' | 'user_invited' | 'case_opened' | 'exception_raised' | 'plan_changed';
  description: string;
  timestamp: string;
}

export interface AdminDashboardProps {
  companies?: AdminCompanyRow[];
  events?: PlatformEvent[];
  loading?: boolean;
  onCompanyClick?: (id: string) => void;
  onCreateCompany?: (data: NewCompanyPayload) => Promise<void>;
}

export interface NewCompanyPayload {
  name: string;
  slug: string;
  plan_tier: PlanTier;
  primary_contact_email: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const TIER_VARIANT: Record<PlanTier, 'info' | 'warning' | 'success'> = {
  basic: 'info',
  hr: 'warning',
  admin: 'success',
};

const EVENT_ICONS: Record<PlatformEvent['type'], string> = {
  company_created: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  user_invited:    'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  case_opened:     'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z',
  exception_raised:'M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z',
  plan_changed:    'M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',
};

const MOCK_COMPANIES: AdminCompanyRow[] = [
  { id: 'c1', name: 'Acme Corp', slug: 'acme', plan_tier: 'admin', case_count: 42, user_count: 18, created_at: '2024-01-15T09:00:00Z', status: 'active' },
  { id: 'c2', name: 'Globex Inc', slug: 'globex', plan_tier: 'hr', case_count: 17, user_count: 9, created_at: '2024-03-20T10:00:00Z', status: 'active' },
  { id: 'c3', name: 'Initech', slug: 'initech', plan_tier: 'basic', case_count: 5, user_count: 3, created_at: '2024-06-01T08:00:00Z', status: 'suspended' },
];

const MOCK_EVENTS: PlatformEvent[] = [
  { id: 'e1', type: 'company_created',  description: 'Acme Corp was onboarded',          timestamp: '2026-05-20T10:00:00Z' },
  { id: 'e2', type: 'user_invited',     description: 'sarah@globex.com invited as HR',    timestamp: '2026-05-20T09:30:00Z' },
  { id: 'e3', type: 'case_opened',      description: 'New case: FR → DE (Marc Bouchard)', timestamp: '2026-05-20T08:45:00Z' },
  { id: 'e4', type: 'exception_raised', description: 'Exception request pending review',  timestamp: '2026-05-19T17:00:00Z' },
  { id: 'e5', type: 'plan_changed',     description: 'Initech upgraded basic → hr',       timestamp: '2026-05-19T15:20:00Z' },
];

// ── Slide-over: New company ───────────────────────────────────────────────────

function NewCompanySlideOver({
  open,
  onClose,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: NewCompanyPayload) => Promise<void>;
}) {
  const [form, setForm] = useState<NewCompanyPayload>({
    name: '',
    slug: '',
    plan_tier: 'basic',
    primary_contact_email: '',
  });
  const [saving, setSaving] = useState(false);

  function field(k: keyof NewCompanyPayload, v: string) {
    setForm(f => ({ ...f, [k]: v }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try { await onSubmit(form); onClose(); } finally { setSaving(false); }
  }

  if (!open) return null;

  return (
    <>
      {/* eslint-disable-next-line local/no-clickable-div -- presentational mouse-dismiss overlay (aria-hidden); panel is keyboard-dismissible via its own controls */}
      <div
        aria-hidden="true"
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'var(--overlay)', zIndex: 'var(--z-overlay)' as never }}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="New company"
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0,
          width: 'var(--drawer-w)',
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: 'var(--shadow-4)',
          zIndex: 'var(--z-panel)' as never,
          display: 'flex', flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>New company</h2>
          <Button unstyled onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </Button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {([
            { id: 'name',  label: 'Company name',          type: 'text',  placeholder: 'Acme Corp' },
            { id: 'slug',  label: 'Slug',                  type: 'text',  placeholder: 'acme-corp' },
            { id: 'primary_contact_email', label: 'Primary contact email', type: 'email', placeholder: 'admin@acme.com' },
          ] as const).map(({ id, label, type, placeholder }) => (
            <label key={id} style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>
              {label}
              <Input unstyled
                type={type}
                required
                placeholder={placeholder}
                value={form[id]}
                onChange={v => field(id, v)}
                style={{ height: 'var(--input-h)', padding: '0 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '14px' }}
              />
            </label>
          ))}

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>
            Plan tier
            <select
              value={form.plan_tier}
              onChange={e => field('plan_tier', e.target.value)}
              style={{ height: 'var(--input-h)', padding: '0 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '14px' }}
            >
              <option value="basic">Basic</option>
              <option value="hr">HR</option>
              <option value="admin">Admin</option>
            </select>
          </label>

          <div style={{ marginTop: 'auto', paddingTop: '16px', display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <Button unstyled type="button" onClick={onClose} style={{ padding: '8px 16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '14px', cursor: 'pointer' }}>
              Cancel
            </Button>
            <Button unstyled
              type="submit"
              disabled={saving}
              style={{ padding: '8px 20px', borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}
            >
              {saving ? 'Creating…' : 'Create company'}
            </Button>
          </div>
        </form>
      </aside>
    </>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function AdminDashboard({
  companies = MOCK_COMPANIES,
  events = MOCK_EVENTS,
  loading = false,
  onCompanyClick,
  onCreateCompany,
}: AdminDashboardProps) {
  const [slideOver, setSlideOver] = useState(false);

  const totalCases = companies.reduce((s, c) => s + c.case_count, 0);
  const activeUsers = companies.reduce((s, c) => s + c.user_count, 0);

  async function handleCreate(data: NewCompanyPayload) {
    await onCreateCompany?.(data);
  }

  return (
    <div style={{ padding: 'var(--page-py) var(--page-px)', maxWidth: 'var(--content-max-w)', display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-3xl)', fontWeight: 700, color: 'var(--text)' }}>Admin dashboard</h1>
          <p style={{ margin: '4px 0 0', fontSize: '14px', color: 'var(--text-muted)' }}>Platform-wide metrics and operations</p>
        </div>
        <Button unstyled
          onClick={() => setSlideOver(true)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '0 18px', height: 'var(--btn-h-md)', borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          New company
        </Button>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <StatCard title="Total companies"       value={companies.length}  icon="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"            iconColor="var(--accent)" />
        <StatCard title="Cases this month"      value={totalCases}        icon="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" iconColor="var(--info)" />
        <StatCard title="Active users"          value={activeUsers}       icon="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" iconColor="var(--success)" />
        <StatCard title="MRR" value="—" delta={undefined} icon="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" iconColor="var(--warning)" />
      </div>

      {/* Main content: companies table + event feed */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '24px', alignItems: 'start' }}>

        {/* Companies table */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: 'var(--text)' }}>Companies</h2>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{companies.length} total</span>
          </div>
          {loading ? (
            <LoadingSpinner centered />
          ) : companies.length === 0 ? (
            <EmptyState icon="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" title="No companies yet" description="Create the first company to get started." action={{ label: 'New company', onClick: () => setSlideOver(true) }} />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: 'var(--surface-2)' }}>
                    {['Company', 'Plan', 'Cases', 'Users', 'Created', 'Status'].map(h => (
                      <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {companies.map(row => (
                    <tr
                      key={row.id}
                      {...(onCompanyClick ? {
                        onClick: () => onCompanyClick(row.id),
                        onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onCompanyClick(row.id); } },
                        role: 'button' as const,
                        tabIndex: 0,
                      } : {})}
                      style={{ cursor: onCompanyClick ? 'pointer' : 'default', borderBottom: '1px solid var(--border)', transition: 'background var(--transition-fast)' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-hover)')}
                      onMouseLeave={e => (e.currentTarget.style.background = '')}
                    >
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Avatar name={row.name} size={28} />
                          <span style={{ fontWeight: 500, color: 'var(--text)' }}>{row.name}</span>
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px' }}><Pill variant={TIER_VARIANT[row.plan_tier]} size="sm">{row.plan_tier}</Pill></td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>{row.case_count}</td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>{row.user_count}</td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-muted)' }}><DateFormatter date={row.created_at} format="absolute" /></td>
                      <td style={{ padding: '12px 16px' }}><Pill variant={row.status === 'active' ? 'success' : 'danger'} size="sm" dot>{row.status}</Pill></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Recent events feed */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)' }}>
            <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: 'var(--text)' }}>Recent events</h2>
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {events.slice(0, 10).map(ev => (
              <li key={ev.id} style={{ display: 'flex', gap: '12px', padding: '12px 20px', borderBottom: '1px solid var(--border)', alignItems: 'flex-start' }}>
                <span style={{ width: '28px', height: '28px', borderRadius: 'var(--radius-md)', background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: '1px' }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d={EVENT_ICONS[ev.type]} />
                  </svg>
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ margin: 0, fontSize: '13px', color: 'var(--text)', lineHeight: 1.4 }}>{ev.description}</p>
                  <p style={{ margin: '3px 0 0', fontSize: '11px', color: 'var(--text-muted)' }}>
                    <DateFormatter date={ev.timestamp} format="relative" />
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <NewCompanySlideOver open={slideOver} onClose={() => setSlideOver(false)} onSubmit={handleCreate} />
    </div>
  );
}

export default AdminDashboard;
