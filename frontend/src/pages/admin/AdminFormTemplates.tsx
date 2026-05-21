/**
 * [P1-2 / Phase 2A] Admin Form Templates — list page.
 *
 * Catalog of official government forms. Shows all (code, version) rows
 * ordered alphabetically. Clicking a row opens the editor (Basic info tab
 * only in Phase 2A; Fields and Trigger rules tabs land in Phase 2B).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Card } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminFormTemplatesAPI, type FormTemplate } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';

const COUNTRY_OPTIONS: Array<{ code: string; label: string }> = [
  { code: '', label: 'All countries' },
  { code: 'NO', label: 'Norway' },
  { code: 'FR', label: 'France' },
  { code: 'DE', label: 'Germany' },
  { code: 'NL', label: 'Netherlands' },
  { code: 'ES', label: 'Spain' },
  { code: 'IT', label: 'Italy' },
  { code: 'CH', label: 'Switzerland' },
  { code: 'GB', label: 'United Kingdom' },
];

export const AdminFormTemplates: React.FC = () => {
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({ country: '', category: '', code: '' });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await adminFormTemplatesAPI.list({
        country: filters.country || undefined,
        category: filters.category || undefined,
        code: filters.code || undefined,
        limit: 200,
      });
      setTemplates(rows);
    } catch (e) {
      setTemplates([]);
      setError((e as Error)?.message || 'Failed to load form templates');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Form templates" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout
      title="Form templates"
      subtitle="Catalog of official government forms. Each row is a (code, version) pair."
    >
      <div className="flex flex-wrap gap-2 mb-4">
        <select
          value={filters.country}
          onChange={(e) => setFilters((f) => ({ ...f, country: e.target.value }))}
          className="rounded border border-slate-200 px-3 py-2 text-sm"
        >
          {COUNTRY_OPTIONS.map((c) => (
            <option key={c.code} value={c.code}>
              {c.label}
            </option>
          ))}
        </select>
        <input
          value={filters.category}
          onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}
          placeholder="Category"
          className="rounded border border-slate-200 px-3 py-2 text-sm w-40"
        />
        <input
          value={filters.code}
          onChange={(e) => setFilters((f) => ({ ...f, code: e.target.value }))}
          placeholder="Code (e.g. UTL-2011)"
          className="rounded border border-slate-200 px-3 py-2 text-sm w-48"
        />
        <Button onClick={() => void load()} disabled={loading}>
          {loading ? 'Loading…' : 'Apply'}
        </Button>
        <Link to={buildRoute('adminFormTemplatesNew')}>
          <Button variant="primary">New template</Button>
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <Card padding="lg">
        <div className="text-sm text-slate-500 mb-2">
          {templates.length} template{templates.length !== 1 ? 's' : ''}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 pr-4">Code</th>
                <th className="text-left py-2 pr-4">Name</th>
                <th className="text-left py-2 pr-4">Country</th>
                <th className="text-left py-2 pr-4">Authority</th>
                <th className="text-left py-2 pr-4">Category</th>
                <th className="text-left py-2 pr-4">Version</th>
                <th className="text-left py-2 pr-4">Fields</th>
                <th className="text-left py-2 pr-4">Updated</th>
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr key={t.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 pr-4 font-mono text-xs">
                    <Link
                      to={buildRoute('adminFormTemplatesEdit', { id: t.id })}
                      className="text-[#0b2b43] hover:underline font-medium"
                    >
                      {t.code}
                    </Link>
                  </td>
                  <td className="py-2 pr-4">{t.name}</td>
                  <td className="py-2 pr-4">{t.country}</td>
                  <td className="py-2 pr-4 text-slate-600">{t.authority_code || '—'}</td>
                  <td className="py-2 pr-4 text-slate-600">{t.category || '—'}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-slate-500">{t.version}</td>
                  <td className="py-2 pr-4 text-slate-500">{t.fields?.length ?? 0}</td>
                  <td className="py-2 pr-4 text-slate-500">
                    {t.updated_at ? new Date(t.updated_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {templates.length === 0 && !loading && !error && (
          <div className="py-8 text-center text-slate-500">
            No form templates yet. Click <span className="font-medium">New template</span> to create the first one.
          </div>
        )}
      </Card>
    </AdminLayout>
  );
};
