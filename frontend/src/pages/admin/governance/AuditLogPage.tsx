import React, { useEffect, useState } from 'react';
import { AdminLayout } from '../AdminLayout';
import { Alert, Badge } from '../../../components/antigravity';
import { Button } from '../../../components/antigravity/Button';
import { listAuditLogs, type AuditLogRow } from '../../../api/governance';

const PAGE = 50;

function actionLabel(r: AuditLogRow): string {
  return (r.event || r.action_type || 'event').replace(/_/g, ' ');
}
function actorLabel(r: AuditLogRow): string {
  return r.actor_name || r.actor_id || 'system';
}
function actionTone(action: string): 'success' | 'warning' | 'error' | 'neutral' {
  if (action === 'insert') return 'success';
  if (action === 'delete') return 'error';
  if (action === 'update') return 'warning';
  return 'neutral';
}

export const AuditLogPage: React.FC = () => {
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [entityType, setEntityType] = useState('');
  const [actionType, setActionType] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await listAuditLogs({
        entity_type: entityType || undefined,
        action_type: actionType || undefined,
        limit: PAGE,
        offset,
      });
      setRows(res.items || []);
      setTotal(res.total || 0);
    } catch {
      setError('Could not load the audit log.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [offset, entityType, actionType]);

  return (
    <AdminLayout title="Audit log" subtitle="Who changed what across the platform">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          value={entityType}
          onChange={(e) => { setOffset(0); setEntityType(e.target.value); }}
          placeholder="Filter by entity (e.g. mobility_cases)"
          aria-label="Entity type filter"
          className="min-w-[14rem] rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <select
          value={actionType}
          onChange={(e) => { setOffset(0); setActionType(e.target.value); }}
          aria-label="Action filter"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">All actions</option>
          <option value="insert">insert</option>
          <option value="update">update</option>
          <option value="delete">delete</option>
        </select>
        <span className="ml-auto text-sm text-slate-400">{total} event{total === 1 ? '' : 's'}</span>
      </div>

      {error && <Alert variant="error" title="Error">{error}</Alert>}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-widest text-slate-400">
            <tr>
              <th className="px-4 py-2">When</th>
              <th className="px-4 py-2">Actor</th>
              <th className="px-4 py-2">Action</th>
              <th className="px-4 py-2">Entity</th>
            </tr>
          </thead>
          <tbody data-testid="audit-rows">
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Loading…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">No audit events.</td></tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-400">{r.created_at?.replace('T', ' ').slice(0, 16)}</td>
                  <td className="px-4 py-2 text-slate-700">{actorLabel(r)}</td>
                  <td className="px-4 py-2">
                    <Badge variant={actionTone(r.action_type)} size="sm">{actionLabel(r)}</Badge>
                  </td>
                  <td className="px-4 py-2 text-slate-500">{r.entity_type}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-end gap-2">
        <Button variant="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
        <Button variant="ghost" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
      </div>
    </AdminLayout>
  );
};
