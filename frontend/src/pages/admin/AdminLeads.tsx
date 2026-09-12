import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import { RefreshButton } from '../../components/RefreshButton';
import { adminLeadsAPI, type LeadRow } from '../../api/client';
import { AdminLayout } from './AdminLayout';

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'new', label: 'New' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'converted', label: 'Converted' },
  { value: 'lost', label: 'Lost' },
];

const NEXT_STATUS: Record<string, string> = {
  new: 'contacted', contacted: 'qualified', qualified: 'converted',
};

function statusBadge(status: string): React.ReactElement {
  const variant =
    status === 'converted' ? 'success'
    : status === 'qualified' ? 'info'
    : status === 'lost' ? 'error'
    : status === 'contacted' ? 'warning'
    : 'info';
  return <Badge variant={variant}>{status}</Badge>;
}

export const AdminLeads: React.FC = () => {
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { status?: string; limit: number } = { limit: 200 };
      if (statusFilter) params.status = statusFilter;
      const res = await adminLeadsAPI.list(params);
      setRows(res.leads);
      setTotal(res.total);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to load leads'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { void load(); }, [load]);

  const advance = async (r: LeadRow) => {
    const next = NEXT_STATUS[r.status];
    if (!next) return;
    await adminLeadsAPI.patch(r.id, { status: next });
    void load();
  };

  return (
    <AdminLayout title="Leads" subtitle="Inbound marketing-site leads and pipeline triage">
      <Card>
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          {STATUS_FILTERS.map((f) => (
            <Button
              key={f.value || 'all'}
              variant={statusFilter === f.value ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-[#6b7280]">{total} total</span>
            <RefreshButton onClick={() => void load()} loading={loading} />
          </div>
        </div>
        {error && <Alert variant="error">{error}</Alert>}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[#6b7280] border-b border-[#e5e7eb]">
              <th className="py-2 pr-3">Email</th>
              <th className="py-2 pr-3">Company</th>
              <th className="py-2 pr-3">Source</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2 pr-3">Match</th>
              <th className="py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-[#f3f4f6] hover:bg-[#f8fafc]">
                <td className="py-2 pr-3 font-medium text-[#0b2b43]">
                  <span className="inline-flex items-center gap-1.5">
                    {r.email}
                    {r.is_test ? <Badge variant="neutral" size="sm">test</Badge> : null}
                  </span>
                </td>
                <td className="py-2 pr-3 text-[#374151]">{r.company_domain || '—'}</td>
                <td className="py-2 pr-3 text-[#374151]">{r.source}</td>
                <td className="py-2 pr-3">{statusBadge(r.status)}</td>
                <td className="py-2 pr-3">
                  {r.matched_prospect ? <Badge variant="success">matched prospect</Badge> : '—'}
                </td>
                <td className="py-2">
                  {NEXT_STATUS[r.status] && (
                    <Button size="sm" variant="outline" onClick={() => void advance(r)}>
                      → {NEXT_STATUS[r.status]}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <p className="text-sm text-[#6b7280] py-6 text-center">No leads yet.</p>
        )}
      </Card>
    </AdminLayout>
  );
};
