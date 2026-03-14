import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge, Select } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type { AdminPolicyCompany, AdminCompany } from '../../types';
import { buildRoute } from '../../navigation/routes';

const POLICY_STATUS_LABELS: Record<string, string> = {
  no_policy: 'No policy',
  draft: 'Draft',
  review_required: 'Review required',
  reviewed: 'Reviewed',
  published: 'Published',
};

const POLICY_STATUS_VARIANTS: Record<string, 'neutral' | 'success' | 'warning'> = {
  no_policy: 'neutral',
  draft: 'neutral',
  review_required: 'warning',
  reviewed: 'neutral',
  published: 'success',
};

function formatDate(val: string | null | undefined): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return val;
  }
}

export const AdminPoliciesPage: React.FC = () => {
  const [rows, setRows] = useState<AdminPolicyCompany[]>([]);
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [filterCompanyId, setFilterCompanyId] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewRes, companiesRes] = await Promise.all([
        adminAPI.listPolicyOverview({ company_id: filterCompanyId || undefined }),
        adminAPI.listCompanies(),
      ]);
      setRows(overviewRes.companies);
      setCompanies(companiesRes.companies);
    } finally {
      setLoading(false);
    }
  }, [filterCompanyId]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  return (
    <AdminLayout
      title="Policies"
      subtitle="Company policy status — inspect, assist, open policy workspace"
    >
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <Select
            label="Company"
            value={filterCompanyId}
            onChange={setFilterCompanyId}
            options={[{ value: '', label: 'All companies' }, ...companies.map((c) => ({ value: c.id, label: c.name }))]}
            placeholder="All companies"
          />
          <Button onClick={load} disabled={loading}>
            {loading ? 'Loading…' : 'Apply'}
          </Button>
        </div>
      </Card>

      <Card padding="lg">
        <div className="text-sm text-[#6b7280] mb-2">Policy status by company ({rows.length})</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280]">
                <th className="py-2 pr-2">Company</th>
                <th className="py-2 pr-2">Status</th>
                <th className="py-2 pr-2">Policy title</th>
                <th className="py-2 pr-2">Latest version</th>
                <th className="py-2 pr-2">Published</th>
                <th className="py-2 pr-2">Last updated</th>
                <th className="py-2 pr-2">Docs</th>
                <th className="py-2 pr-2">Versions</th>
                <th className="py-2 pr-2">Resolved</th>
                <th className="py-2 pr-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.company_id} className="border-b border-[#e2e8f0] hover:bg-[#f8fafc]">
                  <td className="py-2 pr-2 font-medium text-[#0b2b43]">{r.company_name || r.company_id}</td>
                  <td className="py-2 pr-2">
                    <Badge variant={POLICY_STATUS_VARIANTS[r.policy_status] || 'neutral'} size="sm">
                      {POLICY_STATUS_LABELS[r.policy_status] || r.policy_status}
                    </Badge>
                  </td>
                  <td className="py-2 pr-2">{r.policy_title || '—'}</td>
                  <td className="py-2 pr-2">{r.latest_version_number ?? '—'}</td>
                  <td className="py-2 pr-2">
                    {r.policy_status === 'published' ? 'Yes' : r.policy_id ? 'No' : '—'}
                  </td>
                  <td className="py-2 pr-2">{formatDate(r.latest_version_updated_at || r.policy_updated_at)}</td>
                  <td className="py-2 pr-2">{r.doc_count ?? 0}</td>
                  <td className="py-2 pr-2">{r.version_count ?? 0}</td>
                  <td className="py-2 pr-2">{r.resolved_count ?? 0}</td>
                  <td className="py-2 pr-2">
                    <Link
                      to={`${buildRoute('hrPolicy')}?adminCompanyId=${encodeURIComponent(r.company_id)}`}
                    >
                      <Button size="sm" variant="outline">
                        Open workspace
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length === 0 && (
          <div className="py-8 text-center text-[#6b7280]">
            <div className="text-sm font-medium">No policy data</div>
            <div className="text-xs mt-1">No companies with policy records. HR users upload policies in Policy Management.</div>
          </div>
        )}
      </Card>

      <Card padding="lg" className="mt-4">
        <h3 className="text-sm font-medium text-[#374151] mb-2">Policy assistance</h3>
        <ul className="text-sm text-[#4b5563] space-y-1 list-disc list-inside">
          <li><strong>Open workspace</strong> — Opens the HR-style policy workspace for the selected company (upload, normalize, review, publish).</li>
          <li><strong>Docs</strong> — Number of uploaded policy documents (PDF/DOCX) for that company.</li>
          <li><strong>Versions</strong> — Normalized policy versions (from document normalization).</li>
          <li><strong>Resolved</strong> — Assignments with resolved policy (visible to employees).</li>
          <li>HR users manage their own company policy operationally. Admin inspects and assists across all companies.</li>
        </ul>
        <div className="mt-3 flex gap-4">
          <Link to={buildRoute('adminCompanies')} className="text-sm font-medium text-[#0b2b43] hover:underline">
            Companies →
          </Link>
          <Link to={buildRoute('adminPeople')} className="text-sm font-medium text-[#0b2b43] hover:underline">
            People (view-as) →
          </Link>
        </div>
      </Card>
    </AdminLayout>
  );
};
