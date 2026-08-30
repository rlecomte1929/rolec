import React, { useEffect, useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { Alert, Badge, Card } from '../../components/antigravity';
import { Button } from '../../components/antigravity/Button';
import { listErasureRequests, exportUserData, eraseUserData, patchErasureRequest, type ErasureRequest, type ErasureAction } from '../../api/dsar';

const statusTone = (s: string): 'success' | 'warning' | 'error' | 'neutral' =>
  s === 'completed' ? 'success' : s === 'rejected' ? 'error' : s === 'pending' ? 'warning' : 'neutral';

function downloadJson(data: unknown, name: string) {
  try {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  } catch {
    /* download not available (e.g. test env) — the data was still fetched */
  }
}

export const AdminDsarPage: React.FC = () => {
  const [items, setItems] = useState<ErasureRequest[]>([]);
  const [status, setStatus] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [eraseTarget, setEraseTarget] = useState<ErasureRequest | null>(null);
  const [confirmText, setConfirmText] = useState('');
  const [actingId, setActingId] = useState<string | null>(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      const res = await listErasureRequests(status);
      setItems(res.items || []);
    } catch {
      setError('Could not load erasure requests.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [status]);

  async function onExport(userId: string) {
    setError(null);
    try {
      const data = await exportUserData(userId);
      downloadJson(data, `dsar-export-${userId}.json`);
    } catch {
      setError('Export failed.');
    }
  }

  async function onLifecycle(r: ErasureRequest, action: ErasureAction) {
    setError(null);
    setActingId(r.id);
    try {
      await patchErasureRequest(r.id, action);
      await load();
    } catch {
      setError(`Could not ${action} the request.`);
    } finally {
      setActingId(null);
    }
  }

  async function onConfirmErase() {
    if (!eraseTarget?.employee_id || confirmText !== 'DELETE') return;
    setError(null);
    try {
      await eraseUserData(eraseTarget.employee_id);
      setEraseTarget(null); setConfirmText('');
      await load();
    } catch {
      setError('Erasure failed.');
    }
  }

  return (
    <AdminLayout title="Data-rights desk" subtitle="GDPR/DSAR — erasure requests across all tenants">
      <Alert variant="warning">
        Erasure is <strong>permanent</strong> (Art.17) — it deletes/anonymises the subject data and is
        audit-logged. Export is the Art.20 portability copy.
      </Alert>
      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

      <div className="mt-4 mb-3 flex items-center gap-2">
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="all">All statuses</option>
          <option value="pending">pending</option>
          <option value="approved">approved</option>
          <option value="rejected">rejected</option>
          <option value="completed">completed</option>
        </select>
        <span className="ml-auto text-sm text-slate-500">{items.length} requests</span>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-widest text-slate-500">
            <tr>
              <th className="px-4 py-2">Subject</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Requested</th>
              <th className="px-4 py-2">Due</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody data-testid="dsar-rows">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">Loading…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No erasure requests.</td></tr>
            ) : (
              items.map((r) => (
                <tr key={r.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 font-mono text-xs text-slate-700">{r.employee_id || '—'}</td>
                  <td className="px-4 py-2"><Badge variant={statusTone(r.status)} size="sm">{r.status}</Badge></td>
                  <td className="px-4 py-2 text-slate-500">{r.requested_at ? r.requested_at.slice(0, 10) : '—'}</td>
                  <td className="px-4 py-2 text-slate-500">{r.statutory_due_at ? r.statutory_due_at.slice(0, 10) : '—'}</td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    {r.status === 'pending' && (
                      <>
                        <button disabled={actingId === r.id} className="mr-3 text-xs font-medium text-emerald-700 hover:text-emerald-800 disabled:opacity-50" onClick={() => void onLifecycle(r, 'approve')}>
                          Approve
                        </button>
                        <button disabled={actingId === r.id} className="mr-3 text-xs font-medium text-slate-500 hover:text-slate-700 disabled:opacity-50" onClick={() => void onLifecycle(r, 'reject')}>
                          Reject
                        </button>
                      </>
                    )}
                    {r.status === 'approved' && (
                      <button disabled={actingId === r.id} className="mr-3 text-xs font-medium text-emerald-700 hover:text-emerald-800 disabled:opacity-50" onClick={() => void onLifecycle(r, 'complete')}>
                        Mark complete
                      </button>
                    )}
                    {r.employee_id && (
                      <>
                        <button className="mr-3 text-xs font-medium text-accent-700 hover:text-accent-800" onClick={() => void onExport(r.employee_id!)}>
                          Export
                        </button>
                        <button className="text-xs font-medium text-rose-600 hover:text-rose-700" onClick={() => { setEraseTarget(r); setConfirmText(''); }}>
                          Erase
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {eraseTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" data-testid="erase-modal">
          <Card className="w-[28rem] max-w-[90vw]">
            <div className="p-2">
              <p className="font-semibold text-rose-700">Permanently erase subject data</p>
              <p className="mt-1 text-sm text-slate-600">
                This deletes/anonymises all data for <span className="font-mono text-xs">{eraseTarget.employee_id}</span>.
                Type <strong>DELETE</strong> to confirm.
              </p>
              <input
                value={confirmText} onChange={(e) => setConfirmText(e.target.value)}
                aria-label="Type DELETE to confirm" placeholder="DELETE"
                className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <div className="mt-3 flex justify-end gap-2">
                <Button variant="ghost" onClick={() => { setEraseTarget(null); setConfirmText(''); }}>Cancel</Button>
                <Button variant="primary" disabled={confirmText !== 'DELETE'} onClick={() => void onConfirmErase()}>
                  Erase permanently
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </AdminLayout>
  );
};
