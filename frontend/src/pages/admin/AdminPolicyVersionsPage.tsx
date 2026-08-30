import React, { useEffect, useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { Alert, Badge, Card } from '../../components/antigravity';
import {
  listCompaniesForVersions, listPolicyVersions, rollbackToVersion,
  type CompanyOption, type PolicyVersion,
} from '../../api/policyVersions';

const statusTone = (s: string): 'success' | 'warning' | 'neutral' =>
  s === 'published' ? 'success' : s === 'archived' ? 'neutral' : 'warning';

const field = (v: PolicyVersion, key: keyof PolicyVersion) => (v[key] ?? '—') as React.ReactNode;

export const AdminPolicyVersionsPage: React.FC = () => {
  const [companies, setCompanies] = useState<CompanyOption[]>([]);
  const [companyId, setCompanyId] = useState('');
  const [versions, setVersions] = useState<PolicyVersion[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCompaniesForVersions().then(setCompanies).catch(() => setError('Could not load companies.'));
  }, []);

  async function loadVersions(id: string) {
    if (!id) { setVersions([]); return; }
    setLoading(true); setError(null); setPicked([]);
    try {
      setVersions(await listPolicyVersions(id));
    } catch {
      setError('Could not load policy versions for this company.');
    } finally {
      setLoading(false);
    }
  }

  function onPick(id: string) {
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));
  }

  async function onRollback(v: PolicyVersion) {
    if (!window.confirm(`Roll back by re-publishing version ${v.version_number}? The current published version is archived.`)) return;
    setError(null);
    try {
      await rollbackToVersion(v.id);
      await loadVersions(companyId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rollback failed (version may be incomplete or already published).');
    }
  }

  const diff = picked.map((id) => versions.find((v) => v.id === id)).filter(Boolean) as PolicyVersion[];
  const [da, db] = diff;

  return (
    <AdminLayout title="Policy versions" subtitle="Browse policy history, diff, and roll back">
      <Alert variant="info">
        Rollback re-publishes an older version (the current published one is archived) — audit-logged via the
        existing publish path. Incomplete or already-published versions cannot be published.
      </Alert>
      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

      <div className="mt-4 mb-3 flex items-center gap-2">
        <select
          value={companyId}
          onChange={(e) => { setCompanyId(e.target.value); void loadVersions(e.target.value); }}
          aria-label="Company"
          className="min-w-[18rem] rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Select a company…</option>
          {companies.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <span className="text-sm text-slate-500">{versions.length} versions</span>
      </div>

      {da && db && (
        <Card className="mb-4">
          <div className="p-1 text-xs" data-testid="version-diff">
            <p className="mb-2 font-semibold text-navy-800">Compare v{da.version_number} ↔ v{db.version_number}</p>
            <div className="grid grid-cols-3 gap-2">
              <div className="font-medium text-slate-500">Field</div>
              <div className="font-medium text-slate-500">v{da.version_number}</div>
              <div className="font-medium text-slate-500">v{db.version_number}</div>
              {(['status', 'effective_date', 'expiry_date', 'created_at'] as (keyof PolicyVersion)[]).map((k) => (
                <React.Fragment key={k}>
                  <div className="text-slate-500">{k}</div>
                  <div className={da[k] !== db[k] ? 'font-medium text-navy-800' : 'text-slate-600'}>{field(da, k)}</div>
                  <div className={da[k] !== db[k] ? 'font-medium text-navy-800' : 'text-slate-600'}>{field(db, k)}</div>
                </React.Fragment>
              ))}
            </div>
          </div>
        </Card>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-widest text-slate-500">
            <tr>
              <th className="px-4 py-2">Diff</th>
              <th className="px-4 py-2">Version</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Effective</th>
              <th className="px-4 py-2">Created</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody data-testid="version-rows">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">Loading…</td></tr>
            ) : versions.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">{companyId ? 'No versions.' : 'Select a company.'}</td></tr>
            ) : (
              versions.map((v) => (
                <tr key={v.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">
                    <input type="checkbox" aria-label={`compare v${v.version_number}`} checked={picked.includes(v.id)} onChange={() => onPick(v.id)} />
                  </td>
                  <td className="px-4 py-2 font-medium text-slate-700">v{v.version_number}</td>
                  <td className="px-4 py-2"><Badge variant={statusTone(v.status)} size="sm">{v.status}</Badge></td>
                  <td className="px-4 py-2 text-slate-500">{v.effective_date || '—'}</td>
                  <td className="px-4 py-2 text-slate-500">{v.created_at ? v.created_at.slice(0, 10) : '—'}</td>
                  <td className="px-4 py-2 text-right">
                    {v.status !== 'published' && (
                      <button className="text-xs font-medium text-accent-700 hover:text-accent-800" onClick={() => void onRollback(v)}>
                        Roll back to this
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
