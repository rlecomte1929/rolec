/**
 * T13 — HR Control Panel (S7) /hr
 * HR-facing main operations view with stat cards, cases table, and new case modal.
 */

import { useState, useMemo } from 'react';
import {
  StatCard,
  FilterChips,
  Avatar,
  Pill,
  ProgressBar,
  EmptyState,
  DateFormatter,
} from '../shared';
import type { PillVariant } from '../shared';
import { useMovableColumns } from '../data-table/MovableColumns';
import { MovableTh } from '../data-table/MovableColumns';
import type { CaseStatus, CaseStage } from '../../../types/relopass-api-contracts';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CaseRow {
  id: string;
  employee_name: string;
  employee_email: string;
  corridor: string; // e.g. "FR-DE"
  stage: CaseStage;
  status: CaseStatus;
  progress: number; // 0–100
  hr_owner: string;
  target_date: string; // ISO date
}

export interface HRControlPanelProps {
  cases?: CaseRow[];
  onViewCase?: (id: string) => void;
  onCreateCase?: (data: NewCaseData) => void;
}

export interface NewCaseData {
  employee_email: string;
  origin_country: string;
  dest_country: string;
  target_date: string;
}

// ─── Mock ─────────────────────────────────────────────────────────────────────

const MOCK_CASES: CaseRow[] = [
  { id: 'c1', employee_name: 'Alice Martin', employee_email: 'alice@co.com', corridor: 'FR-DE', stage: 'compliance', status: 'active', progress: 45, hr_owner: 'Sophie L.', target_date: '2026-07-01' },
  { id: 'c2', employee_name: 'Bob Chen', employee_email: 'bob@co.com', corridor: 'US-GB', stage: 'housing', status: 'active', progress: 62, hr_owner: 'Marc D.', target_date: '2026-06-15' },
  { id: 'c3', employee_name: 'Clara Singh', employee_email: 'clara@co.com', corridor: 'IN-NL', stage: 'intake', status: 'on_hold', progress: 12, hr_owner: 'Sophie L.', target_date: '2026-08-01' },
  { id: 'c4', employee_name: 'David Lee', employee_email: 'david@co.com', corridor: 'KR-DE', stage: 'logistics', status: 'active', progress: 78, hr_owner: 'Marc D.', target_date: '2026-05-30' },
  { id: 'c5', employee_name: 'Eva Torres', employee_email: 'eva@co.com', corridor: 'ES-FR', stage: 'close_out', status: 'completed', progress: 100, hr_owner: 'Sophie L.', target_date: '2026-05-20' },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STATUS_VARIANT: Record<CaseStatus, PillVariant> = {
  draft: 'muted',
  active: 'success',
  on_hold: 'warning',
  completed: 'info',
  cancelled: 'danger',
};

const STATUS_LABEL: Record<CaseStatus, string> = {
  draft: 'Draft',
  active: 'Active',
  on_hold: 'On Hold',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

const STAGE_LABEL: Record<CaseStage, string> = {
  intake: 'Intake',
  compliance: 'Compliance',
  housing: 'Housing',
  logistics: 'Logistics',
  settling_in: 'Settling In',
  close_out: 'Close Out',
};

const FILTER_CHIPS = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'Active' },
  { id: 'on_hold', label: 'Blocked' },
  { id: 'completed', label: 'Completed' },
];

const TABLE_COLUMNS = [
  { id: 'employee', label: 'Employee', minWidth: 160 },
  { id: 'corridor', label: 'Corridor', minWidth: 90 },
  { id: 'stage', label: 'Stage', minWidth: 110 },
  { id: 'status', label: 'Status', minWidth: 90 },
  { id: 'progress', label: 'Progress', minWidth: 120 },
  { id: 'hr_owner', label: 'HR Owner', minWidth: 100 },
  { id: 'target_date', label: 'Target date', minWidth: 120 },
  { id: 'actions', label: 'Actions', minWidth: 80, fixed: true },
];

// ─── New Case Modal ───────────────────────────────────────────────────────────

interface NewCaseModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: NewCaseData) => void;
}

function NewCaseModal({ open, onClose, onSubmit }: NewCaseModalProps) {
  const [form, setForm] = useState<NewCaseData>({ employee_email: '', origin_country: '', dest_country: '', target_date: '' });

  if (!open) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(form);
    setForm({ employee_email: '', origin_country: '', dest_country: '', target_date: '' });
    onClose();
  }

  const field = (label: string, key: keyof NewCaseData, type = 'text', placeholder = '') => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <label style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</label>
      <input
        type={type}
        placeholder={placeholder}
        value={form[key]}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        required
        style={{
          padding: '8px 12px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border)',
          background: 'var(--surface)',
          color: 'var(--text)',
          fontSize: '14px',
          outline: 'none',
        }}
      />
    </div>
  );

  return (
    <>
      <div aria-hidden="true" onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'var(--overlay)', zIndex: 40 }} />
      <div
        role="dialog"
        aria-label="New case"
        style={{
          position: 'fixed',
          top: 0, right: 0, bottom: 0,
          width: '400px',
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>New case</h2>
          <button onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {field('Employee email', 'employee_email', 'email', 'employee@company.com')}
          {field('Origin country (ISO-2)', 'origin_country', 'text', 'e.g. FR')}
          {field('Destination country (ISO-2)', 'dest_country', 'text', 'e.g. DE')}
          {field('Target start date', 'target_date', 'date')}
          <div style={{ marginTop: 'auto', paddingTop: '8px' }}>
            <button
              type="submit"
              style={{ width: '100%', padding: '10px', borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer' }}
            >
              Create case
            </button>
          </div>
        </form>
      </div>
    </>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function HRControlPanel({ cases = MOCK_CASES, onViewCase, onCreateCase }: HRControlPanelProps) {
  const [filter, setFilter] = useState('all');
  const [modalOpen, setModalOpen] = useState(false);

  const { orderedColumns, thProps } = useMovableColumns({ tableId: 'hr-cases', columns: TABLE_COLUMNS });

  const filtered = useMemo(() => {
    if (filter === 'all') return cases;
    return cases.filter(c => c.status === filter);
  }, [cases, filter]);

  const stats = useMemo(() => ({
    total: cases.length,
    active: cases.filter(c => c.status === 'active').length,
    blocked: cases.filter(c => c.status === 'on_hold').length,
    dueThisWeek: cases.filter(c => {
      const d = new Date(c.target_date);
      const now = new Date();
      const week = 7 * 24 * 60 * 60 * 1000;
      return d.getTime() - now.getTime() < week && d.getTime() > now.getTime();
    }).length,
  }), [cases]);

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1 style={{ margin: 0, fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>HR Control Panel</h1>
        <button
          onClick={() => setModalOpen(true)}
          style={{ padding: '9px 16px', borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--accent)', color: '#fff', fontSize: '14px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14" /></svg>
          New case
        </button>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '28px' }}>
        <StatCard title="Total cases" value={stats.total} delta="+2 this month" icon="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2" />
        <StatCard title="Active" value={stats.active} delta="+1" iconColor="var(--success)" icon="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 0 0 1.946-.806 3.42 3.42 0 0 1 4.438 0 3.42 3.42 0 0 0 1.946.806" />
        <StatCard title="Blocked" value={stats.blocked} delta={stats.blocked > 0 ? `+${stats.blocked}` : '0'} iconColor="var(--danger)" icon="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <StatCard title="Due this week" value={stats.dueThisWeek} iconColor="var(--warning)" icon="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" />
      </div>

      {/* Filter chips */}
      <div style={{ marginBottom: '16px' }}>
        <FilterChips chips={FILTER_CHIPS} selected={filter} onSelect={setFilter} />
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <EmptyState icon="M9 5H7a2 2 0 0 0-2 2v12" title="No cases found" description="Try a different filter." />
      ) : (
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                  {orderedColumns.map(col => (
                    <MovableTh key={col.id} {...thProps(col)} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }} />
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((row, i) => (
                  <tr
                    key={row.id}
                    style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--border)' : 'none', transition: 'background 0.1s' }}
                    onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)'}
                    onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = ''}
                  >
                    {orderedColumns.map(col => (
                      <td key={col.id} style={{ padding: '12px 14px', verticalAlign: 'middle' }}>
                        {col.id === 'employee' && (
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <Avatar name={row.employee_name} size={28} />
                            <div>
                              <p style={{ margin: 0, fontWeight: 600, color: 'var(--text)' }}>{row.employee_name}</p>
                              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>{row.employee_email}</p>
                            </div>
                          </div>
                        )}
                        {col.id === 'corridor' && <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{row.corridor}</span>}
                        {col.id === 'stage' && <Pill variant="default" size="sm">{STAGE_LABEL[row.stage]}</Pill>}
                        {col.id === 'status' && <Pill variant={STATUS_VARIANT[row.status]} size="sm" dot>{STATUS_LABEL[row.status]}</Pill>}
                        {col.id === 'progress' && (
                          <div style={{ minWidth: '100px' }}>
                            <ProgressBar value={row.progress} height={6} label={`${row.progress}%`} />
                          </div>
                        )}
                        {col.id === 'hr_owner' && (
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <Avatar name={row.hr_owner} size={24} />
                            <span style={{ color: 'var(--text-secondary)' }}>{row.hr_owner}</span>
                          </div>
                        )}
                        {col.id === 'target_date' && <DateFormatter date={row.target_date} format="absolute" />}
                        {col.id === 'actions' && (
                          <button
                            onClick={() => onViewCase?.(row.id)}
                            style={{ padding: '5px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--accent)', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                          >
                            View
                          </button>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <NewCaseModal open={modalOpen} onClose={() => setModalOpen(false)} onSubmit={data => onCreateCase?.(data)} />
    </div>
  );
}
