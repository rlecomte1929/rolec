/**
 * AdminExceptions.tsx — T19 / S1e  /admin/exceptions
 * ─────────────────────────────────────────────────────────────────────────────
 * Global exceptions view for admin+ roles.
 * Filter chips · exceptions table · Approve / Deny with ConfirmDialog + notes
 */

import { useState } from 'react';
import {
  Pill,
  Avatar,
  DateFormatter,
  EmptyState,
  FilterChips,
  LoadingSpinner,
} from '../shared';
import type { ExceptionStatus } from '../../../types/relopass-api-contracts';

// ── Local types ───────────────────────────────────────────────────────────────

export interface AdminException {
  id: string;
  employee_name: string;
  company_name: string;
  benefit: string;
  requested_value: string;
  policy_value: string;
  justification: string;
  status: ExceptionStatus;
  created_at: string;
}

export interface AdminExceptionsProps {
  exceptions?: AdminException[];
  loading?: boolean;
  onApprove?: (id: string, notes: string) => Promise<void>;
  onDeny?: (id: string, notes: string) => Promise<void>;
}

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_EXCEPTIONS: AdminException[] = [
  {
    id: 'exc-001',
    employee_name: 'Marc Bouchard',
    company_name: 'Acme Corp',
    benefit: 'International school',
    requested_value: '€18,000/yr',
    policy_value: 'Excluded',
    justification: 'Two children mid-year, only international school available in destination.',
    status: 'pending',
    created_at: '2026-05-19T09:00:00Z',
  },
  {
    id: 'exc-002',
    employee_name: 'Li Wei',
    company_name: 'Globex Inc',
    benefit: 'Temp housing',
    requested_value: '90 days',
    policy_value: '60 days',
    justification: 'Visa delay pushed permanent housing search back by a month.',
    status: 'approved',
    created_at: '2026-05-15T14:00:00Z',
  },
  {
    id: 'exc-003',
    employee_name: 'Ana Ribeiro',
    company_name: 'Acme Corp',
    benefit: 'Moving allowance',
    requested_value: '€12,000',
    policy_value: '€8,000',
    justification: 'Relocating from São Paulo — shipping costs significantly higher than EU baseline.',
    status: 'denied',
    created_at: '2026-05-10T11:00:00Z',
  },
  {
    id: 'exc-004',
    employee_name: 'Tom Fischer',
    company_name: 'Initech',
    benefit: 'Pet relocation',
    requested_value: '€3,500',
    policy_value: '€1,500',
    justification: 'Two large dogs; airline quotes exceeded policy cap by €2,000.',
    status: 'pending',
    created_at: '2026-05-20T08:00:00Z',
  },
];

// ── Filter config ─────────────────────────────────────────────────────────────

const FILTER_CHIPS = [
  { id: 'all',      label: 'All' },
  { id: 'pending',  label: 'Pending' },
  { id: 'approved', label: 'Approved' },
  { id: 'denied',   label: 'Denied' },
];

type FilterId = 'all' | ExceptionStatus;

const STATUS_VARIANT: Record<ExceptionStatus, 'warning' | 'success' | 'danger'> = {
  pending:  'warning',
  approved: 'success',
  denied:   'danger',
};

// ── Confirm dialog with notes ─────────────────────────────────────────────────

interface ActionDialog {
  open: boolean;
  kind: 'approve' | 'deny';
  exceptionId: string;
  notes: string;
}

// ── Main component ────────────────────────────────────────────────────────────

export function AdminExceptions({
  exceptions = MOCK_EXCEPTIONS,
  loading = false,
  onApprove,
  onDeny,
}: AdminExceptionsProps) {
  const [filter, setFilter] = useState<FilterId>('all');
  const [dialog, setDialog] = useState<ActionDialog>({ open: false, kind: 'approve', exceptionId: '', notes: '' });
  const [saving, setSaving] = useState(false);

  const visible = filter === 'all' ? exceptions : exceptions.filter(e => e.status === filter);

  function openDialog(kind: 'approve' | 'deny', id: string) {
    setDialog({ open: true, kind, exceptionId: id, notes: '' });
  }

  async function handleConfirm() {
    setSaving(true);
    try {
      if (dialog.kind === 'approve') await onApprove?.(dialog.exceptionId, dialog.notes);
      else await onDeny?.(dialog.exceptionId, dialog.notes);
      setDialog(d => ({ ...d, open: false }));
    } finally {
      setSaving(false);
    }
  }

  const counts: Record<FilterId, number> = {
    all:      exceptions.length,
    pending:  exceptions.filter(e => e.status === 'pending').length,
    approved: exceptions.filter(e => e.status === 'approved').length,
    denied:   exceptions.filter(e => e.status === 'denied').length,
  };

  const chipsWithCounts = FILTER_CHIPS.map(c => ({ ...c, count: counts[c.id as FilterId] }));

  return (
    <div style={{ padding: 'var(--page-py) var(--page-px)', maxWidth: 'var(--content-max-w)', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ margin: 0, fontSize: 'var(--text-3xl)', fontWeight: 700, color: 'var(--text)' }}>Policy exceptions</h1>
        <p style={{ margin: '4px 0 0', fontSize: '14px', color: 'var(--text-muted)' }}>Review and action exception requests across all companies</p>
      </div>

      {/* Filter chips */}
      <FilterChips chips={chipsWithCounts} selected={filter} onSelect={(id: string) => setFilter(id as FilterId)} />

      {/* Table */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        {loading ? (
          <LoadingSpinner centered />
        ) : visible.length === 0 ? (
          <EmptyState
            icon="M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"
            title={`No ${filter === 'all' ? '' : filter} exceptions`}
            description="Nothing here — check another filter or come back later."
          />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)' }}>
                  {['Employee', 'Company', 'Benefit', 'Requested', 'Policy', 'Justification', 'Status', 'Created', 'Actions'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map(ex => (
                  <tr key={ex.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Avatar name={ex.employee_name} size={26} />
                        <span style={{ fontWeight: 500, color: 'var(--text)', whiteSpace: 'nowrap' }}>{ex.employee_name}</span>
                      </div>
                    </td>
                    <td style={{ padding: '12px 14px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{ex.company_name}</td>
                    <td style={{ padding: '12px 14px', color: 'var(--text)', whiteSpace: 'nowrap' }}>{ex.benefit}</td>
                    <td style={{ padding: '12px 14px', fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap' }}>{ex.requested_value}</td>
                    <td style={{ padding: '12px 14px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{ex.policy_value}</td>
                    <td style={{ padding: '12px 14px', maxWidth: '220px' }}>
                      <span
                        title={ex.justification}
                        style={{
                          display: 'block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          color: 'var(--text-secondary)',
                          fontSize: '12px',
                        }}
                      >
                        {ex.justification}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <Pill variant={STATUS_VARIANT[ex.status]} size="sm" dot>{ex.status}</Pill>
                    </td>
                    <td style={{ padding: '12px 14px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      <DateFormatter date={ex.created_at} format="relative" />
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      {ex.status === 'pending' ? (
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            onClick={() => openDialog('approve', ex.id)}
                            style={{ padding: '5px 10px', fontSize: '12px', fontWeight: 600, borderRadius: 'var(--radius-sm)', border: '1px solid var(--pill-success-border)', background: 'var(--pill-success-bg)', color: 'var(--pill-success-text)', cursor: 'pointer' }}
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => openDialog('deny', ex.id)}
                            style={{ padding: '5px 10px', fontSize: '12px', fontWeight: 600, borderRadius: 'var(--radius-sm)', border: '1px solid var(--pill-danger-border)', background: 'var(--pill-danger-bg)', color: 'var(--pill-danger-text)', cursor: 'pointer' }}
                          >
                            Deny
                          </button>
                        </div>
                      ) : (
                        <span style={{ fontSize: '12px', color: 'var(--text-disabled)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Confirm dialog with notes */}
      {dialog.open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={dialog.kind === 'approve' ? 'Approve exception' : 'Deny exception'}
          style={{ position: 'fixed', inset: 0, zIndex: 'var(--z-modal)' as never, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div aria-hidden="true" onClick={() => setDialog(d => ({ ...d, open: false }))} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(2px)' }} />
          <div style={{ position: 'relative', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-4)', padding: '24px', maxWidth: '440px', width: '90vw', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h2 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>
              {dialog.kind === 'approve' ? 'Approve exception' : 'Deny exception'}
            </h2>
            <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {dialog.kind === 'approve'
                ? 'The requester will be notified that their exception has been approved.'
                : 'The requester will be notified that their exception has been denied.'}
            </p>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>
              Notes (optional)
              <textarea
                rows={3}
                value={dialog.notes}
                onChange={e => setDialog(d => ({ ...d, notes: e.target.value }))}
                placeholder="Add a note for the requester…"
                style={{ padding: '10px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: '13px', resize: 'vertical', lineHeight: 1.5 }}
              />
            </label>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setDialog(d => ({ ...d, open: false }))} style={{ padding: '8px 16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '14px', cursor: 'pointer' }}>
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={saving}
                style={{
                  padding: '8px 20px', borderRadius: 'var(--radius-md)', border: 'none',
                  background: dialog.kind === 'approve' ? 'var(--success)' : 'var(--danger)',
                  color: '#fff', fontSize: '14px', fontWeight: 600,
                  cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1,
                }}
              >
                {saving ? 'Saving…' : dialog.kind === 'approve' ? 'Approve' : 'Deny'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminExceptions;
