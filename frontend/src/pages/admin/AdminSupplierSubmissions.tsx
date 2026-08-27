/**
 * AIQ-1602 Seg 4 — admin review of HR-proposed suppliers (moderation queue).
 * Approve promotes the proposal into public.suppliers; reject requires a note.
 * Mirrors AdminVettingQueue.tsx.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Card, Button, Alert, Badge } from '../../components/antigravity';
import {
  listSupplierSubmissions,
  resolveSupplierSubmission,
  type AdminSupplierSubmission,
} from '../../api/adminSupplierSubmissions';
import { AdminLayout } from './AdminLayout';

function errMessage(err: unknown, fallback: string): string {
  const msg =
    err && typeof err === 'object' && 'response' in err
      ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : (err as Error)?.message;
  return String(msg || fallback);
}

const STATUS_TONE: Record<AdminSupplierSubmission['status'], 'warning' | 'success' | 'neutral'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'neutral',
};

export const AdminSupplierSubmissions: React.FC = () => {
  const [items, setItems] = useState<AdminSupplierSubmission[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectNotes, setRejectNotes] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSupplierSubmissions(statusFilter || undefined);
      setItems(data.submissions || []);
    } catch (err: unknown) {
      setError(errMessage(err, 'Failed to load supplier submissions'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const approve = useCallback(
    async (row: AdminSupplierSubmission) => {
      setSaving(true);
      setError(null);
      try {
        await resolveSupplierSubmission(row.id, 'approve');
        await load();
      } catch (err: unknown) {
        setError(errMessage(err, 'Failed to approve submission'));
      } finally {
        setSaving(false);
      }
    },
    [load],
  );

  const reject = useCallback(
    async (row: AdminSupplierSubmission, notes: string) => {
      if (!notes.trim()) return;
      setSaving(true);
      setError(null);
      try {
        await resolveSupplierSubmission(row.id, 'reject', notes.trim());
        setRejectingId(null);
        setRejectNotes('');
        await load();
      } catch (err: unknown) {
        setError(errMessage(err, 'Failed to reject submission'));
      } finally {
        setSaving(false);
      }
    },
    [load],
  );

  return (
    <AdminLayout
      title="Supplier submissions"
      subtitle="HR-proposed suppliers awaiting a platform review decision"
    >
      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <div className="mb-4 flex items-center gap-2">
        <label htmlFor="sub-status" className="text-sm text-[#6b7280]">
          Status
        </label>
        <select
          id="sub-status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-1.5 text-sm text-[#0b2b43]"
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="">All</option>
        </select>
      </div>

      {loading ? (
        <Card padding="lg">
          <div className="text-sm text-[#6b7280]">Loading…</div>
        </Card>
      ) : items.length === 0 ? (
        <Card padding="lg">
          <div className="text-sm text-[#6b7280]">
            No {statusFilter || ''} supplier submissions.
          </div>
        </Card>
      ) : (
        <ul className="space-y-3">
          {items.map((row) => (
            <li key={row.id}>
              <Card padding="lg">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#0b2b43]">{row.name}</span>
                      <Badge variant={STATUS_TONE[row.status]} size="sm">
                        {row.status}
                      </Badge>
                    </div>
                    <div className="text-sm text-[#64748b] mt-1">
                      {row.service_category}
                      {row.city_name ? ` · ${row.city_name}` : ''}
                      {row.country_code ? `, ${row.country_code}` : ''}
                      {row.contact_email ? ` · ${row.contact_email}` : ''}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      Company {row.company_id}
                      {row.created_supplier_id ? ` · supplier ${row.created_supplier_id}` : ''}
                    </div>
                    {row.review_notes && (
                      <p className="text-xs text-[#b91c1c] mt-1">Note: {row.review_notes}</p>
                    )}
                  </div>
                  {row.status === 'pending' && (
                    <div className="flex items-center gap-2 shrink-0">
                      <Button size="sm" onClick={() => void approve(row)} disabled={saving}>
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setRejectingId(row.id);
                          setRejectNotes('');
                        }}
                        disabled={saving}
                      >
                        Reject
                      </Button>
                    </div>
                  )}
                </div>

                {rejectingId === row.id && (
                  <div className="mt-3 border-t border-[#e2e8f0] pt-3">
                    <label htmlFor={`rej-${row.id}`} className="block text-sm text-[#0b2b43]">
                      Reason for rejection (sent to HR)
                    </label>
                    <textarea
                      id={`rej-${row.id}`}
                      value={rejectNotes}
                      onChange={(e) => setRejectNotes(e.target.value)}
                      rows={2}
                      className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
                    />
                    <div className="mt-2 flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => void reject(row, rejectNotes)}
                        disabled={saving || !rejectNotes.trim()}
                      >
                        Confirm reject
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setRejectingId(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </AdminLayout>
  );
};
