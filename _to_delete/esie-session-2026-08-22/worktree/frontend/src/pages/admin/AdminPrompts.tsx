import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, Button, Alert, Badge, Input } from '../../components/antigravity';
import { promptsAPI, PromptVersion, WinRate } from '../../api/client';
import { AdminLayout } from './AdminLayout';

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'info' | 'neutral'> = {
  prod: 'success',
  canary: 'warning',
  draft: 'info',
  archived: 'neutral',
};

function statusVariant(status: string): 'success' | 'warning' | 'info' | 'neutral' {
  return STATUS_VARIANT[status] || 'neutral';
}

// Parker Step E — format a version's human-feedback win rate for the table cell.
function formatWinRate(wr: WinRate | undefined): { label: string; title: string } {
  if (!wr || wr.total === 0) {
    return { label: '—', title: 'No human review verdicts yet' };
  }
  const pct = (wr.win_rate * 100).toFixed(0);
  const lo = (wr.ci_low * 100).toFixed(0);
  const hi = (wr.ci_high * 100).toFixed(0);
  return {
    label: `${pct}% (${wr.approvals}/${wr.total})`,
    title: `Wilson 95% CI: ${lo}–${hi}% · ${wr.approvals} approved of ${wr.total} verdicts`,
  };
}

export const AdminPrompts: React.FC = () => {
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [winRates, setWinRates] = useState<Record<string, Record<string, WinRate>>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await promptsAPI.list();
      setVersions(rows);
      // Parker Step E — fetch win rates per task_key (best-effort; never blocks the table).
      const taskKeys = Array.from(new Set(rows.map((r) => r.task_key)));
      const entries = await Promise.all(
        taskKeys.map(async (taskKey) => {
          try {
            return [taskKey, await promptsAPI.winRates(taskKey)] as const;
          } catch {
            return [taskKey, {}] as const;
          }
        })
      );
      setWinRates(Object.fromEntries(entries));
    } catch (e) {
      setError('Failed to load prompts.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Group versions by task_key for rendering one table per task.
  const byTask = useMemo(() => {
    const map = new Map<string, PromptVersion[]>();
    for (const v of versions) {
      const list = map.get(v.task_key) || [];
      list.push(v);
      map.set(v.task_key, list);
    }
    for (const list of map.values()) {
      list.sort((a, b) => b.version - a.version);
    }
    return map;
  }, [versions]);

  const promote = useCallback(
    async (version: PromptVersion, target: string) => {
      setBusyId(version.id);
      setError(null);
      try {
        await promptsAPI.promote(version.id, target);
        await load();
      } catch (e) {
        setError(`Failed to ${target === 'prod' ? 'promote' : 'update'} version ${version.version}.`);
      } finally {
        setBusyId(null);
      }
    },
    [load]
  );

  return (
    <AdminLayout title="Prompts" subtitle="Versioned LLM system prompts + canary A/B">
      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      {loading && versions.length === 0 ? (
        <p className="text-slate-500">Loading…</p>
      ) : byTask.size === 0 ? (
        <Card>
          <p className="text-slate-600">
            No prompt versions yet. Apply the prompt registry migration to seed the
            current prompts.
          </p>
        </Card>
      ) : (
        Array.from(byTask.entries()).map(([taskKey, rows]) => (
          <div key={taskKey} className="mb-8">
            <h2 className="text-lg font-semibold text-slate-900 mb-2">{taskKey}</h2>
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-slate-200">
                      <th className="py-2 pr-4 font-medium">Version</th>
                      <th className="py-2 pr-4 font-medium">Status</th>
                      <th className="py-2 pr-4 font-medium">Model</th>
                      <th className="py-2 pr-4 font-medium">Max tokens</th>
                      <th className="py-2 pr-4 font-medium">Win rate</th>
                      <th className="py-2 pr-4 font-medium">Notes</th>
                      <th className="py-2 pr-4 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((v) => (
                      <tr key={v.id} className="border-b border-slate-100 align-top">
                        <td className="py-2 pr-4 font-mono">v{v.version}</td>
                        <td className="py-2 pr-4">
                          <Badge variant={statusVariant(v.status)}>{v.status}</Badge>
                        </td>
                        <td className="py-2 pr-4 font-mono text-slate-700">{v.model_name}</td>
                        <td className="py-2 pr-4 text-slate-700">{v.max_tokens}</td>
                        {(() => {
                          const wr = formatWinRate(winRates[taskKey]?.[v.id]);
                          return (
                            <td className="py-2 pr-4 text-slate-700 whitespace-nowrap" title={wr.title}>
                              {wr.label}
                            </td>
                          );
                        })()}
                        <td className="py-2 pr-4 text-slate-500 max-w-xs truncate" title={v.notes || ''}>
                          {v.notes || '—'}
                        </td>
                        <td className="py-2 pr-4">
                          <div className="flex gap-2">
                            {v.status !== 'prod' && (
                              <Button
                                size="sm"
                                variant="primary"
                                disabled={busyId === v.id}
                                onClick={() => void promote(v, 'prod')}
                              >
                                Promote
                              </Button>
                            )}
                            {v.status !== 'archived' && v.status !== 'prod' && (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={busyId === v.id}
                                onClick={() => void promote(v, 'archived')}
                              >
                                Archive
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <CanaryShareControl taskKey={taskKey} onError={setError} />
            </Card>
          </div>
        ))
      )}
    </AdminLayout>
  );
};

const CanaryShareControl: React.FC<{
  taskKey: string;
  onError: (msg: string | null) => void;
}> = ({ taskKey, onError }) => {
  const [value, setValue] = useState('0');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const save = useCallback(async () => {
    const share = Number(value);
    if (Number.isNaN(share) || share < 0 || share > 1) {
      onError('Canary share must be between 0 and 1.');
      return;
    }
    setSaving(true);
    setSaved(false);
    onError(null);
    try {
      await promptsAPI.setCanaryShare(taskKey, share);
      setSaved(true);
    } catch (e) {
      onError('Failed to update canary share.');
    } finally {
      setSaving(false);
    }
  }, [taskKey, value, onError]);

  return (
    <div className="mt-4 flex items-end gap-3">
      <div className="w-40">
        <Input
          label="Canary share (0–1)"
          type="number"
          value={value}
          onChange={(v) => {
            setValue(v);
            setSaved(false);
          }}
        />
      </div>
      <Button size="sm" variant="secondary" disabled={saving} onClick={() => void save()}>
        Save
      </Button>
      {saved && <span className="text-sm text-emerald-600 pb-2">Saved</span>}
    </div>
  );
};

export default AdminPrompts;
