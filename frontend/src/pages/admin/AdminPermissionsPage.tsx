import React, { useMemo, useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { Alert } from '../../components/antigravity';
import { buildPermissionsMatrix, MATRIX_ROLES, type MatrixRole } from '../../lib/permissionsMatrix';

const cell = (on: boolean) =>
  on ? <span className="text-accent-700" aria-label="yes">✓</span> : <span className="text-slate-500" aria-label="no">—</span>;

export const AdminPermissionsPage: React.FC = () => {
  const [filter, setFilter] = useState('');
  const rows = useMemo(() => buildPermissionsMatrix(), []);
  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? rows.filter((r) => r.path.toLowerCase().includes(q) || r.key.toLowerCase().includes(q)) : rows;
  }, [rows, filter]);

  return (
    <AdminLayout title="Permissions matrix" subtitle="Declared route access by role — who can reach what">
      <Alert variant="info">
        Declared route access from the route registry. The <strong>authoritative</strong> boundary is the
        backend dependency gate (<code>require_admin</code> etc.) and the per-route guard — this matrix shows
        the declared intent, and a test keeps it in sync with the registry.
      </Alert>

      <div className="mt-4 mb-3 flex items-center gap-3">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by path or name…"
          aria-label="Filter routes"
          className="min-w-[18rem] rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <span className="text-sm text-slate-500">{shown.length} of {rows.length} routes</span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-widest text-slate-500">
            <tr>
              <th className="px-4 py-2">Route</th>
              <th className="px-4 py-2">Path</th>
              {MATRIX_ROLES.map((role) => (
                <th key={role} className="px-4 py-2 text-center">{role}</th>
              ))}
            </tr>
          </thead>
          <tbody data-testid="permissions-rows">
            {shown.map((r) => (
              <tr key={r.key} className="border-t border-slate-100">
                <td className="px-4 py-2 font-medium text-slate-700">{r.key}</td>
                <td className="px-4 py-2 font-mono text-xs text-slate-500">{r.path}</td>
                {MATRIX_ROLES.map((role: MatrixRole) => (
                  <td key={role} className="px-4 py-2 text-center">{cell(r.access[role])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
};
