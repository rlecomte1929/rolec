/**
 * AdminCompanies.tsx — T20 / S9x  /admin/companies
 * ─────────────────────────────────────────────────────────────────────────────
 * Company management table for admin+ roles.
 * Toolbar · MovableColumns table · Edit slide-over · Suspend/Activate toggle
 */

import { useState, useMemo } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { Pill, FilterChips, Avatar, DateFormatter, EmptyState, LoadingSpinner } from '../shared';
import { useMovableColumns, MovableTh } from '../data-table/MovableColumns';
import type { PlanTier } from '../../../types/relopass-api-contracts';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AdminCompanyRecord {
  id: string;
  name: string;
  slug: string;
  plan_tier: PlanTier;
  case_count: number;
  user_count: number;
  created_at: string;
  status: 'active' | 'suspended';
  primary_contact_email: string;
}

export interface AdminCompaniesProps {
  companies?: AdminCompanyRecord[];
  loading?: boolean;
  onEdit?: (id: string, data: EditCompanyPayload) => Promise<void>;
  onToggleStatus?: (id: string, nextStatus: 'active' | 'suspended') => Promise<void>;
  onViewCases?: (id: string) => void;
  onNewCompany?: () => void;
}

export interface EditCompanyPayload {
  name: string;
  plan_tier: PlanTier;
  primary_contact_email: string;
  status: 'active' | 'suspended';
}

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_COMPANIES: AdminCompanyRecord[] = [
  { id: 'c1', name: 'Acme Corp',   slug: 'acme',   plan_tier: 'admin', case_count: 42, user_count: 18, created_at: '2024-01-15T09:00:00Z', status: 'active',    primary_contact_email: 'admin@acme.com' },
  { id: 'c2', name: 'Globex Inc',  slug: 'globex', plan_tier: 'hr',    case_count: 17, user_count:  9, created_at: '2024-03-20T10:00:00Z', status: 'active',    primary_contact_email: 'ops@globex.com' },
  { id: 'c3', name: 'Initech',     slug: 'initech',plan_tier: 'basic', case_count:  5, user_count:  3, created_at: '2024-06-01T08:00:00Z', status: 'suspended', primary_contact_email: 'it@initech.com' },
  { id: 'c4', name: 'Umbrella Ltd',slug: 'umbrella',plan_tier:'hr',    case_count: 28, user_count: 12, created_at: '2025-01-10T12:00:00Z', status: 'active',    primary_contact_email: 'hr@umbrella.com' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const TIER_VARIANT: Record<PlanTier, 'info' | 'warning' | 'success'> = {
  basic: 'info',
  hr: 'warning',
  admin: 'success',
};

const PLAN_FILTERS = [
  { id: 'all',   label: 'All' },
  { id: 'basic', label: 'Basic' },
  { id: 'hr',    label: 'HR' },
  { id: 'admin', label: 'Admin' },
];

type PlanFilter = 'all' | PlanTier;

// ── Column definitions ────────────────────────────────────────────────────────

const COLUMNS = [
  { id: 'name',    label: 'Company',  minWidth: 160, fixed: true },
  { id: 'slug',    label: 'Slug',     minWidth: 100 },
  { id: 'tier',    label: 'Plan',     minWidth: 80 },
  { id: 'cases',   label: 'Cases',    minWidth: 70 },
  { id: 'users',   label: 'Users',    minWidth: 70 },
  { id: 'created', label: 'Created',  minWidth: 110 },
  { id: 'status',  label: 'Status',   minWidth: 90 },
  { id: 'actions', label: 'Actions',  minWidth: 160, fixed: true },
];

// ── Edit slide-over ───────────────────────────────────────────────────────────

function EditCompanySlideOver({
  company,
  onClose,
  onSave,
}: {
  company: AdminCompanyRecord;
  onClose: () => void;
  onSave: (data: EditCompanyPayload) => Promise<void>;
}) {
  const [form, setForm] = useState<EditCompanyPayload>({
    name: company.name,
    plan_tier: company.plan_tier,
    primary_contact_email: company.primary_contact_email,
    status: company.status,
  });
  const [saving, setSaving] = useState(false);

  function field<K extends keyof EditCompanyPayload>(k: K, v: EditCompanyPayload[K]) {
    setForm(f => ({ ...f, [k]: v }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try { await onSave(form); onClose(); } finally { setSaving(false); }
  }

  return (
    <>
      <div aria-hidden="true" onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'var(--overlay)', zIndex: 'var(--z-overlay)' as never }} />
      <aside
        role="dialog" aria-modal="true" aria-label="Edit company"
        style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 'var(--drawer-w)', background: 'var(--surface)', borderLeft: '1px solid var(--border)', boxShadow: 'var(--shadow-4)', zIndex: 'var(--z-panel)' as never, display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>Edit company</h2>
          <Button unstyled onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </Button>
        </div>
        <form onSubmit={handleSubmit} style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {([
            { id: 'name',  label: 'Company name', type: 'text' },
            { id: 'primary_contact_email', label: 'Primary contact email', type: 'email' },
          ] as const).map(({ id, label, type }) => (
            <label key={id} style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>
              {label}
              <Input unstyled
                type={type}
                required
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
              onChange={e => field('plan_tier', e.target.value as PlanTier)}
              style={{ height: 'var(--input-h)', padding: '0 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '14px' }}
            >
              <option value="basic">Basic</option>
              <option value="hr">HR</option>
              <option value="admin">Admin</option>
            </select>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={form.status === 'active'}
              onChange={e => field('status', e.target.checked ? 'active' : 'suspended')}
              style={{ width: '16px', height: '16px', accentColor: 'var(--accent)', cursor: 'pointer' }}
            />
            Active
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
              {saving ? 'Saving…' : 'Save changes'}
            </Button>
          </div>
        </form>
      </aside>
    </>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function AdminCompanies({
  companies = MOCK_COMPANIES,
  loading = false,
  onEdit,
  onToggleStatus,
  onViewCases,
  onNewCompany,
}: AdminCompaniesProps) {
  const [search, setSearch] = useState('');
  const [planFilter, setPlanFilter] = useState<PlanFilter>('all');
  const [editTarget, setEditTarget] = useState<AdminCompanyRecord | null>(null);

  const { orderedColumns, thProps } = useMovableColumns({ tableId: 'admin-companies', columns: COLUMNS });

  const filtered = useMemo(() => {
    let rows = companies;
    if (planFilter !== 'all') rows = rows.filter(c => c.plan_tier === planFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(c => c.name.toLowerCase().includes(q) || c.slug.toLowerCase().includes(q));
    }
    return rows;
  }, [companies, planFilter, search]);

  async function handleEdit(data: EditCompanyPayload) {
    if (!editTarget) return;
    await onEdit?.(editTarget.id, data);
  }

  function renderCell(col: { id: string }, row: AdminCompanyRecord) {
    switch (col.id) {
      case 'name':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Avatar name={row.name} size={28} />
            <span style={{ fontWeight: 500, color: 'var(--text)' }}>{row.name}</span>
          </div>
        );
      case 'slug':
        return <code style={{ fontSize: '12px', color: 'var(--text-muted)', background: 'var(--surface-2)', padding: '2px 6px', borderRadius: 'var(--radius-sm)' }}>{row.slug}</code>;
      case 'tier':
        return <Pill variant={TIER_VARIANT[row.plan_tier]} size="sm">{row.plan_tier}</Pill>;
      case 'cases':
        return <span style={{ color: 'var(--text-secondary)' }}>{row.case_count}</span>;
      case 'users':
        return <span style={{ color: 'var(--text-secondary)' }}>{row.user_count}</span>;
      case 'created':
        return <DateFormatter date={row.created_at} format="absolute" style={{ fontSize: '12px', color: 'var(--text-muted)' }} />;
      case 'status':
        return <Pill variant={row.status === 'active' ? 'success' : 'danger'} size="sm" dot>{row.status}</Pill>;
      case 'actions':
        return (
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <Button unstyled
              onClick={() => setEditTarget(row)}
              style={{ padding: '4px 10px', fontSize: '12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', cursor: 'pointer' }}
            >
              Edit
            </Button>
            <Button unstyled
              onClick={() => onToggleStatus?.(row.id, row.status === 'active' ? 'suspended' : 'active')}
              style={{
                padding: '4px 10px', fontSize: '12px', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                border: `1px solid ${row.status === 'active' ? 'var(--pill-danger-border)' : 'var(--pill-success-border)'}`,
                background: row.status === 'active' ? 'var(--pill-danger-bg)' : 'var(--pill-success-bg)',
                color: row.status === 'active' ? 'var(--pill-danger-text)' : 'var(--pill-success-text)',
              }}
            >
              {row.status === 'active' ? 'Suspend' : 'Activate'}
            </Button>
            <Button unstyled
              onClick={() => onViewCases?.(row.id)}
              style={{ padding: '4px 10px', fontSize: '12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--accent)', cursor: 'pointer', whiteSpace: 'nowrap' }}
            >
              Cases
            </Button>
          </div>
        );
      default:
        return null;
    }
  }

  return (
    <div style={{ padding: 'var(--page-py) var(--page-px)', maxWidth: 'var(--content-max-w)', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-3xl)', fontWeight: 700, color: 'var(--text)' }}>Companies</h1>
          <p style={{ margin: '4px 0 0', fontSize: '14px', color: 'var(--text-muted)' }}>Manage all tenant companies on the platform</p>
        </div>
        <Button unstyled
          onClick={onNewCompany}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '0 18px', height: 'var(--btn-h-md)', borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          New company
        </Button>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 220px', maxWidth: '320px' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
          <Input unstyled
            type="search"
            placeholder="Search companies…"
            value={search}
            onChange={v => setSearch(v)}
            style={{ width: '100%', height: 'var(--input-h)', padding: '0 12px 0 32px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '13px' }}
          />
        </div>
        <FilterChips chips={PLAN_FILTERS} selected={planFilter} onSelect={id => setPlanFilter(id as PlanFilter)} />
      </div>

      {/* Table */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        {loading ? (
          <LoadingSpinner centered />
        ) : filtered.length === 0 ? (
          <EmptyState icon="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" title="No companies found" description="Try adjusting your search or filters." />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)' }}>
                  {orderedColumns.map(col => (
                    <MovableTh key={col.id} {...thProps(col)} />
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(row => (
                  <tr
                    key={row.id}
                    style={{ borderBottom: '1px solid var(--border)', transition: 'background var(--transition-fast)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-hover)')}
                    onMouseLeave={e => (e.currentTarget.style.background = '')}
                  >
                    {orderedColumns.map(col => (
                      <td key={col.id} style={{ padding: '12px 14px', verticalAlign: 'middle' }}>
                        {renderCell(col, row)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editTarget && (
        <EditCompanySlideOver
          company={editTarget}
          onClose={() => setEditTarget(null)}
          onSave={handleEdit}
        />
      )}
    </div>
  );
}

export default AdminCompanies;
