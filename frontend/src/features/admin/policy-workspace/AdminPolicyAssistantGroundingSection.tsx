import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Card } from '../../../components/antigravity';
import { adminAPI } from '../../../api/client';

type SnapshotRow = Record<string, unknown> & {
  id?: string;
  revision_number?: number;
  activation_state?: string;
  status?: string;
  created_at?: string;
  activated_at?: string;
};

type HistoryDoc = {
  document: {
    id: string;
    filename?: string;
    uploaded_at?: string;
    uploaded_by_user_id?: string;
    assistant_import_status?: string;
  };
  snapshots: SnapshotRow[];
  processing_runs: Record<string, unknown>[];
};

type HistoryPayload = {
  company_id: string;
  documents: HistoryDoc[];
  active_snapshot?: SnapshotRow | null;
  company_binding?: Record<string, unknown> | null;
  message?: string;
};

export const AdminPolicyAssistantGroundingSection: React.FC<{ companyId: string }> = ({ companyId }) => {
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [olderSnap, setOlderSnap] = useState('');
  const [newerSnap, setNewerSnap] = useState('');
  const [diff, setDiff] = useState<Record<string, unknown> | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const h = (await adminAPI.getPolicyAssistantCompanyHistory(companyId)) as HistoryPayload;
      setHistory(h);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to load history');
      setHistory(null);
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  const allSnapshots = useMemo(() => {
    const rows: SnapshotRow[] = [];
    for (const d of history?.documents ?? []) {
      for (const s of d.snapshots ?? []) {
        rows.push(s);
      }
    }
    return rows;
  }, [history]);

  const runDiff = async () => {
    if (!olderSnap || !newerSnap) return;
    setDiffLoading(true);
    setDiff(null);
    try {
      const out = await adminAPI.getPolicyAssistantSnapshotDiff(companyId, olderSnap, newerSnap);
      setDiff(out as Record<string, unknown>);
    } catch (e: unknown) {
      setDiff({ error: e instanceof Error ? e.message : 'diff failed' });
    } finally {
      setDiffLoading(false);
    }
  };

  const active = history?.active_snapshot;

  return (
    <Card padding="lg" className="mt-8 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 mb-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Policy assistant grounding</h2>
          <p className="text-sm text-slate-600">
            Document uploads, extraction runs, snapshot revisions, and activation for the assistant.
          </p>
        </div>
        <button
          type="button"
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-50"
          onClick={() => load()}
          disabled={loading}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {err && <p className="text-sm text-red-600 mb-3">{err}</p>}

      {history?.message === 'tables_missing' && (
        <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md p-3 mb-4">
          Policy assistant tables are not available in this environment. Apply migrations to enable history.
        </p>
      )}

      {active && (
        <div className="mb-6 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
          <div className="font-medium">Active snapshot for assistant</div>
          <div className="mt-1 font-mono text-xs break-all">id: {String(active.id)}</div>
          <div className="mt-1 text-emerald-900">
            state: {String(active.activation_state || active.status || '')}
            {active.activated_at ? ` · activated ${String(active.activated_at)}` : ''}
          </div>
        </div>
      )}

      {!active && history && !history.message && (
        <p className="text-sm text-slate-600 mb-4">No active snapshot for this company yet.</p>
      )}

      <h3 className="text-sm font-semibold text-slate-800 mb-2">Uploaded documents</h3>
      <div className="overflow-x-auto border border-slate-200 rounded-md">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2">File</th>
              <th className="px-3 py-2">Uploaded</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Revisions</th>
            </tr>
          </thead>
          <tbody>
            {(history?.documents ?? []).map((d) => (
              <tr key={d.document.id} className="border-t border-slate-100">
                <td className="px-3 py-2 font-mono text-xs break-all">{d.document.filename || d.document.id}</td>
                <td className="px-3 py-2 text-slate-700">{d.document.uploaded_at || '—'}</td>
                <td className="px-3 py-2">{d.document.assistant_import_status || '—'}</td>
                <td className="px-3 py-2">{d.snapshots?.length ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="text-sm font-semibold text-slate-800 mt-8 mb-2">Snapshot revisions</h3>
      <ul className="text-sm space-y-1 max-h-48 overflow-y-auto border border-slate-200 rounded-md p-3 bg-slate-50/50">
        {allSnapshots.map((s) => (
          <li key={String(s.id)} className="font-mono text-xs break-all flex flex-wrap gap-x-2">
            <span>{String(s.id)}</span>
            <span className="text-slate-500">
              rev {String(s.revision_number ?? '?')} · {String(s.activation_state || s.status || '')}
            </span>
            {s.created_at ? <span className="text-slate-400">{String(s.created_at)}</span> : null}
          </li>
        ))}
        {allSnapshots.length === 0 && <li className="text-slate-500">No snapshots yet.</li>}
      </ul>

      <h3 className="text-sm font-semibold text-slate-800 mt-8 mb-2">Compare revisions</h3>
      <p className="text-xs text-slate-600 mb-2">
        Paste two snapshot IDs (older vs newer). Summary counts and per-fact diffs load from the server.
      </p>
      <div className="flex flex-wrap gap-2 items-end">
        <label className="flex flex-col text-xs text-slate-600">
          Older snapshot
          <input
            className="mt-1 border border-slate-300 rounded px-2 py-1 text-xs font-mono w-72 max-w-full"
            value={olderSnap}
            onChange={(e) => setOlderSnap(e.target.value)}
            placeholder="snapshot uuid"
          />
        </label>
        <label className="flex flex-col text-xs text-slate-600">
          Newer snapshot
          <input
            className="mt-1 border border-slate-300 rounded px-2 py-1 text-xs font-mono w-72 max-w-full"
            value={newerSnap}
            onChange={(e) => setNewerSnap(e.target.value)}
            placeholder="snapshot uuid"
          />
        </label>
        <button
          type="button"
          className="rounded-md bg-slate-900 text-white px-3 py-1.5 text-sm disabled:opacity-50"
          onClick={() => runDiff()}
          disabled={diffLoading || !olderSnap || !newerSnap}
        >
          {diffLoading ? 'Comparing…' : 'Compare'}
        </button>
      </div>

      {diff && (
        <pre className="mt-4 text-xs bg-slate-900 text-slate-100 p-3 rounded-md overflow-x-auto max-h-96">
          {JSON.stringify(diff, null, 2)}
        </pre>
      )}

      <p className="mt-8 text-xs text-slate-500">
        Draft editing and review/publish for the structured matrix remain on the compensation workspace above; this
        section is for document-grounded assistant evidence only.
      </p>
    </Card>
  );
};
