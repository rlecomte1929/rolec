import React, { useCallback, useEffect, useState } from 'react';
import { AdminLayout } from '../AdminLayout';
import { Button, Card } from '../../../components/antigravity';
import {
  listWorkItems,
  syncWorkItems,
  retriageWorkItem,
  patchWorkItem,
  dispatchWorkItem,
  planWorkItem,
  approvePlan,
  type WorkItem,
} from '../../../api/missionControl';

const STATUSES = ['new', 'triaged', 'planned', 'dispatched', 'in_review', 'done', 'wont_do', 'blocked'];

function priorityChip(p: string): string {
  const m: Record<string, string> = {
    P0: 'bg-rose-100 text-rose-700', P1: 'bg-amber-100 text-amber-700',
    P2: 'bg-sky-100 text-sky-700', P3: 'bg-slate-100 text-slate-600',
  };
  return m[p] ?? 'bg-slate-100 text-slate-600';
}
function kindChip(k: string): string {
  const m: Record<string, string> = {
    bug: 'bg-rose-50 text-rose-700', idea: 'bg-sky-50 text-sky-700',
    quality: 'bg-amber-50 text-amber-700', task: 'bg-slate-100 text-slate-600',
  };
  return m[k] ?? 'bg-slate-100 text-slate-600';
}

export const MissionControlPage: React.FC = () => {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [tableReady, setTableReady] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listWorkItems();
      setItems(res.items);
      setTableReady(res.table_ready);
    } catch {
      setError('Could not load demands.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onSync() {
    setBusy(true);
    try {
      await syncWorkItems();
      await load();
    } catch {
      setError('Sync failed.');
    } finally {
      setBusy(false);
    }
  }

  async function onStatus(id: string, status: string) {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, status } : it)));
    try {
      await patchWorkItem(id, { status });
    } catch {
      void load();
    }
  }

  async function onRetriage(id: string) {
    try {
      await retriageWorkItem(id);
      await load();
    } catch {
      /* best-effort */
    }
  }

  async function onExecute(it: WorkItem) {
    if (!window.confirm(`Dispatch the agent to open a fix PR for "${it.title}"?`)) return;
    setError(null);
    try {
      await dispatchWorkItem(it.id);
      await load();
    } catch {
      setError('Dispatch failed — check it is agent-eligible and dispatch is enabled.');
    }
  }

  async function onPlan(id: string) {
    setBusy(true);
    try {
      await planWorkItem(id);
      await load();
    } catch {
      setError('Could not draft a plan right now.');
    } finally {
      setBusy(false);
    }
  }

  async function onApprovePlan(id: string) {
    try {
      await approvePlan(id);
      await load();
    } catch {
      /* best-effort */
    }
  }

  return (
    <AdminLayout
      title="Mission Control"
      subtitle="Every bug, idea and quality signal — unified, triaged, and ranked. Execution comes next."
      headerRight={
        <Button variant="primary" onClick={() => void onSync()} disabled={busy}>
          {busy ? 'Syncing…' : 'Sync demands'}
        </Button>
      }
    >
      {!tableReady && (
        <Card>
          <p className="p-2 text-sm text-amber-700" data-testid="store-not-ready">
            The demand store isn&apos;t applied yet. Apply the <code>work_items</code> migration, then click
            <strong> Sync demands</strong> to populate this console.
          </p>
        </Card>
      )}

      {error && <p className="text-sm text-rose-600">{error}</p>}
      {loading && <p className="text-sm text-slate-400">Loading demands…</p>}

      {!loading && tableReady && items.length === 0 && (
        <Card>
          <p className="p-2 text-sm text-slate-500" data-testid="empty">
            No demands yet. Click <strong>Sync demands</strong> to pull from feedback + support.
          </p>
        </Card>
      )}

      <div className="space-y-3" data-testid="demands">
        {items.map((it) => (
          <Card key={it.id}>
            <div className="space-y-2 p-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${priorityChip(it.priority)}`}>{it.priority}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${kindChip(it.kind)}`}>{it.kind}</span>
                {it.auto_fixable && (
                  <span className="rounded-full bg-accent-50 px-2 py-0.5 text-xs font-medium text-accent-700">agent-eligible</span>
                )}
                <span className="text-xs text-slate-400">{it.source}</span>
                <span className="ml-auto">
                  <select
                    aria-label={`Status for ${it.title}`}
                    value={it.status}
                    onChange={(e) => void onStatus(it.id, e.target.value)}
                    className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-700"
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </span>
              </div>
              <p className="text-sm font-medium text-slate-800">{it.title}</p>
              {it.body && <p className="line-clamp-2 text-xs text-slate-500">{it.body}</p>}
              {it.plan_json && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs" data-testid="plan">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="font-semibold text-navy-800">Plan</span>
                    {it.plan_json.risk && (
                      <span className={`rounded-full px-2 py-0.5 ${it.plan_json.risk === 'high' ? 'bg-rose-100 text-rose-700' : it.plan_json.risk === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-accent-50 text-accent-700'}`}>
                        risk: {it.plan_json.risk}
                      </span>
                    )}
                    {it.plan_json.approved ? (
                      <span className="ml-auto rounded-full bg-accent-50 px-2 py-0.5 text-accent-700">✓ Approved</span>
                    ) : (
                      <button className="ml-auto font-medium text-accent-700 hover:text-accent-800" onClick={() => void onApprovePlan(it.id)}>
                        Approve plan
                      </button>
                    )}
                  </div>
                  {it.plan_json.summary && <p className="text-slate-700">{it.plan_json.summary}</p>}
                  {it.plan_json.affected_files && it.plan_json.affected_files.length > 0 && (
                    <p className="mt-1 text-slate-500">Files: {it.plan_json.affected_files.join(', ')}</p>
                  )}
                  {it.plan_json.approach && <p className="mt-1 text-slate-500"><span className="font-medium">Approach:</span> {it.plan_json.approach}</p>}
                  {it.plan_json.test_plan && <p className="mt-1 text-slate-500"><span className="font-medium">Tests:</span> {it.plan_json.test_plan}</p>}
                </div>
              )}
              <div className="flex items-center gap-3 text-xs text-slate-400">
                {it.triage_json?.rationale && <span>🧭 {it.triage_json.rationale}</span>}
                {it.source_url && (
                  <a href={it.source_url} className="text-accent-700 underline" target="_blank" rel="noopener noreferrer">source</a>
                )}
                <span className="ml-auto flex items-center gap-3">
                  {it.pr_url && (
                    <a href={it.pr_url} className="text-accent-700 underline" target="_blank" rel="noopener noreferrer">PR ↗</a>
                  )}
                  {it.auto_fixable && !it.triage_json?.blocked && (
                    <button className="font-medium text-accent-700 hover:text-accent-800" onClick={() => void onExecute(it)}>
                      Execute →
                    </button>
                  )}
                  <button className="text-slate-500 hover:text-navy-800" onClick={() => void onPlan(it.id)} disabled={busy}>
                    Plan
                  </button>
                  <button className="text-slate-500 hover:text-navy-800" onClick={() => void onRetriage(it.id)}>
                    Re-triage
                  </button>
                </span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </AdminLayout>
  );
};
