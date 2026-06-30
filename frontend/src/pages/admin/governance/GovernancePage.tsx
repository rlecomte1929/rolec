import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { Alert, Badge, Card } from '../../../components/antigravity';
import { Button } from '../../../components/antigravity/Button';
import { ROUTE_DEFS } from '../../../navigation/routes';
import { listAllowlist, grantAdmin, revokeAdmin, type AllowlistEntry } from '../../../api/governance';

export const GovernancePage: React.FC = () => {
  const [items, setItems] = useState<AllowlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await listAllowlist();
      setItems(res.items || []);
    } catch {
      setError('Could not load the admin allowlist.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function onGrant(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const value = email.trim().toLowerCase();
    if (!value.endsWith('@relopass.com')) {
      setError('Admin emails must end with @relopass.com.');
      return;
    }
    setBusy(true);
    try {
      await grantAdmin(value);
      setEmail('');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not grant admin access.');
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(target: string) {
    if (!window.confirm(`Revoke admin access for ${target}?`)) return;
    setError(null);
    try {
      await revokeAdmin(target);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not revoke — is this the last admin, or yourself?');
    }
  }

  const active = items.filter((i) => i.enabled !== 0);

  return (
    <AdminLayout title="Governance" subtitle="Who can administer the platform — grant or revoke admin access">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-slate-500">{active.length} active admin{active.length === 1 ? '' : 's'}</p>
        <Link to={ROUTE_DEFS.adminAuditLog.path} className="text-sm font-medium text-accent-700 hover:text-accent-800">
          View audit log →
        </Link>
      </div>

      {error && <Alert variant="error" title="Action failed">{error}</Alert>}

      <Card className="mt-3">
        <form onSubmit={onGrant} className="flex flex-wrap items-center gap-2 p-1">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="new.admin@relopass.com"
            aria-label="Admin email"
            className="min-w-[16rem] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <Button type="submit" variant="primary" disabled={busy}>Grant admin</Button>
        </form>
      </Card>

      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-widest text-slate-400">
            <tr>
              <th className="px-4 py-2">Email</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Added</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody data-testid="allowlist-rows">
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Loading…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">No admins on the allowlist.</td></tr>
            ) : (
              items.map((it) => (
                <tr key={it.email} className="border-t border-slate-100">
                  <td className="px-4 py-2 font-medium text-slate-800">{it.email}</td>
                  <td className="px-4 py-2">
                    {it.enabled === 0
                      ? <Badge variant="neutral" size="sm">revoked</Badge>
                      : <Badge variant="success" size="sm">active</Badge>}
                  </td>
                  <td className="px-4 py-2 text-slate-400">{it.created_at ? it.created_at.slice(0, 10) : '—'}</td>
                  <td className="px-4 py-2 text-right">
                    {it.enabled !== 0 && (
                      <button className="text-xs font-medium text-rose-600 hover:text-rose-700" onClick={() => void onRevoke(it.email)}>
                        Revoke
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
