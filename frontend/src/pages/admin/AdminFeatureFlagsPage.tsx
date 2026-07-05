import React, { useEffect, useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { Alert, Badge, Card } from '../../components/antigravity';
import { Button } from '../../components/antigravity/Button';
import {
  listFeatureFlags, upsertFeatureFlag, patchFeatureFlag, addFlagAccount, removeFlagAccount,
  type FeatureFlagRow,
} from '../../api/featureFlags';

export const AdminFeatureFlagsPage: React.FC = () => {
  const [items, setItems] = useState<FeatureFlagRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newKey, setNewKey] = useState('');
  const [newDesc, setNewDesc] = useState('');

  async function load() {
    setLoading(true);
    try {
      const res = await listFeatureFlags();
      setItems(res.items || []);
    } catch {
      setError('Could not load feature flags.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function onToggle(row: FeatureFlagRow) {
    setError(null);
    try {
      await patchFeatureFlag(row.key, { enabled: !row.enabled });
      await load();
    } catch {
      setError(`Could not toggle ${row.key}.`);
    }
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const key = newKey.trim();
    if (!key) return;
    setError(null);
    try {
      await upsertFeatureFlag({ key, enabled: false, description: newDesc.trim() || undefined });
      setNewKey(''); setNewDesc('');
      await load();
    } catch {
      setError('Could not create the flag.');
    }
  }

  async function onAddAccount(key: string) {
    const account = window.prompt(`Add an account id to the "${key}" allowlist:`);
    if (!account) return;
    setError(null);
    try {
      await addFlagAccount(key, account.trim());
      await load();
    } catch {
      setError('Could not add the account.');
    }
  }

  async function onRemoveAccount(key: string) {
    const account = window.prompt(`Remove an account id from the "${key}" allowlist:`);
    if (!account) return;
    setError(null);
    try {
      await removeFlagAccount(key, account.trim());
      await load();
    } catch {
      setError('Could not remove the account.');
    }
  }

  return (
    <AdminLayout title="Feature flags" subtitle="Toggle DB-backed flags without a redeploy">
      <Alert variant="info">
        DB flags take effect immediately (no redeploy). An <strong>enabled</strong> flag with no allowlisted
        accounts is global; add accounts to scope it to selected tenants.
      </Alert>
      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

      <Card className="mt-3">
        <form onSubmit={onCreate} className="flex flex-wrap items-center gap-2 p-1">
          <input
            value={newKey} onChange={(e) => setNewKey(e.target.value)}
            placeholder="flag_key" aria-label="New flag key"
            className="min-w-[12rem] rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            value={newDesc} onChange={(e) => setNewDesc(e.target.value)}
            placeholder="description (optional)" aria-label="New flag description"
            className="min-w-[16rem] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <Button type="submit" variant="primary">Create flag</Button>
        </form>
      </Card>

      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-widest text-slate-400">
            <tr>
              <th className="px-4 py-2">Flag</th>
              <th className="px-4 py-2">State</th>
              <th className="px-4 py-2">Accounts</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody data-testid="flag-rows">
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Loading…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">No feature flags.</td></tr>
            ) : (
              items.map((row) => (
                <tr key={row.key} className="border-t border-slate-100">
                  <td className="px-4 py-2">
                    <div className="font-mono text-xs font-medium text-slate-800">{row.key}</div>
                    {row.description && <div className="text-xs text-slate-400">{row.description}</div>}
                  </td>
                  <td className="px-4 py-2">
                    {row.enabled
                      ? <Badge variant="success" size="sm">on</Badge>
                      : <Badge variant="neutral" size="sm">off</Badge>}
                  </td>
                  <td className="px-4 py-2 text-slate-500">
                    {row.account_count === 0 ? <span className="text-slate-400">global</span> : `${row.account_count} scoped`}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button className="mr-3 text-xs font-medium text-accent-700 hover:text-accent-800" onClick={() => void onToggle(row)}>
                      {row.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button className="mr-3 text-xs text-slate-500 hover:text-navy-800" onClick={() => void onAddAccount(row.key)}>
                      + account
                    </button>
                    {row.account_count > 0 && (
                      <button className="text-xs text-slate-500 hover:text-navy-800" onClick={() => void onRemoveAccount(row.key)}>
                        − account
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
};
