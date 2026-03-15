import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge, Select } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type {
  AdminCompany,
  AdminPoliciesByCompany,
  AdminPolicySummary,
  AdminPolicyDetail,
  AdminPolicyVersion,
} from '../../types';
import { buildRoute } from '../../navigation/routes';

const VERSION_STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  review_required: 'Review required',
  reviewed: 'Reviewed',
  published: 'Published',
  archived: 'Archived',
  auto_generated: 'Auto-generated',
};

const VERSION_STATUS_VARIANTS: Record<string, 'neutral' | 'success' | 'warning'> = {
  draft: 'neutral',
  review_required: 'warning',
  reviewed: 'neutral',
  published: 'success',
  archived: 'neutral',
  auto_generated: 'neutral',
};

function formatDate(val: string | null | undefined): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return String(val);
  }
}

export const AdminPoliciesPage: React.FC = () => {
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const [data, setData] = useState<AdminPoliciesByCompany | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inspectPolicyId, setInspectPolicyId] = useState<string | null>(null);
  const [inspectDetail, setInspectDetail] = useState<AdminPolicyDetail | null>(null);
  const [editPolicyId, setEditPolicyId] = useState<string | null>(null);
  const [editDetail, setEditDetail] = useState<AdminPolicyDetail | null>(null);
  const [editForm, setEditForm] = useState<{ title: string; version: string; effective_date: string }>({ title: '', version: '', effective_date: '' });
  const [saving, setSaving] = useState(false);

  const loadCompanies = useCallback(async () => {
    const res = await adminAPI.listCompanies();
    setCompanies(res.companies);
  }, []);

  const loadPolicies = useCallback(async (companyId: string) => {
    if (!companyId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await adminAPI.listAdminPolicies(companyId);
      setData(result);
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e && typeof (e as { response?: { data?: { detail?: string } } }).response?.data?.detail === 'string'
        ? (e as { response: { data: { detail: string } } }).response.data.detail
        : 'Failed to load policies';
      setError(msg);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCompanies().catch(() => undefined);
  }, [loadCompanies]);

  useEffect(() => {
    if (selectedCompanyId) {
      loadPolicies(selectedCompanyId).catch(() => undefined);
    } else {
      setData(null);
      setError(null);
    }
  }, [selectedCompanyId, loadPolicies]);

  const openInspect = useCallback(async (policyId: string) => {
    setInspectPolicyId(policyId);
    setInspectDetail(null);
    try {
      const detail = await adminAPI.getAdminPolicyDetail(policyId);
      setInspectDetail(detail);
    } catch {
      setInspectDetail(null);
    }
  }, []);

  const closeInspect = useCallback(() => {
    setInspectPolicyId(null);
    setInspectDetail(null);
  }, []);

  const openEdit = useCallback(async (policyId: string) => {
    setEditPolicyId(policyId);
    setEditDetail(null);
    setEditForm({ title: '', version: '', effective_date: '' });
    try {
      const detail = await adminAPI.getAdminPolicyDetail(policyId);
      setEditDetail(detail);
      setEditForm({
        title: (detail.title as string) ?? '',
        version: (detail.version as string) ?? '',
        effective_date: (detail.effective_date as string) ?? '',
      });
    } catch {
      setEditDetail(null);
    }
  }, []);

  const closeEdit = useCallback(() => {
    setEditPolicyId(null);
    setEditDetail(null);
    setSaving(false);
  }, []);

  const saveEdit = useCallback(async () => {
    if (!editPolicyId || !editDetail) return;
    setSaving(true);
    try {
      const payload: { title?: string; version?: string; effective_date?: string } = {};
      if (editForm.title !== (editDetail.title ?? '')) payload.title = editForm.title;
      if (editForm.version !== (editDetail.version ?? '')) payload.version = editForm.version;
      if (editForm.effective_date !== (editDetail.effective_date ?? '')) payload.effective_date = editForm.effective_date || undefined;
      if (Object.keys(payload).length > 0) {
        await adminAPI.patchAdminPolicy(editPolicyId, payload);
      }
      closeEdit();
      if (selectedCompanyId) loadPolicies(selectedCompanyId).catch(() => undefined);
    } finally {
      setSaving(false);
    }
  }, [editPolicyId, editDetail, editForm, selectedCompanyId, loadPolicies, closeEdit]);

  const publishVersion = useCallback(async (policyId: string, versionId: string) => {
    try {
      await adminAPI.patchAdminPolicy(policyId, { publish_version_id: versionId });
      if (inspectPolicyId === policyId) {
        const detail = await adminAPI.getAdminPolicyDetail(policyId);
        setInspectDetail(detail);
      }
      if (editPolicyId === policyId) {
        const detail = await adminAPI.getAdminPolicyDetail(policyId);
        setEditDetail(detail);
      }
      if (selectedCompanyId) loadPolicies(selectedCompanyId).catch(() => undefined);
    } catch {
      // leave UI as is
    }
  }, [inspectPolicyId, editPolicyId, selectedCompanyId, loadPolicies]);

  const unpublishPolicy = useCallback(async (policyId: string) => {
    try {
      await adminAPI.patchAdminPolicy(policyId, { unpublish: true });
      if (inspectPolicyId === policyId) {
        const detail = await adminAPI.getAdminPolicyDetail(policyId);
        setInspectDetail(detail);
      }
      if (editPolicyId === policyId) {
        const detail = await adminAPI.getAdminPolicyDetail(policyId);
        setEditDetail(detail);
      }
      if (selectedCompanyId) loadPolicies(selectedCompanyId).catch(() => undefined);
    } catch {
      // leave UI as is
    }
  }, [inspectPolicyId, editPolicyId, selectedCompanyId, loadPolicies]);

  const policies: AdminPolicySummary[] = data?.policies ?? [];
  const companyName = data?.company_name ?? companies.find((c) => c.id === selectedCompanyId)?.name ?? '';
  const sourceDocCount = data?.source_document_count ?? 0;

  return (
    <AdminLayout
      title="Policies"
      subtitle="Company-scoped policy management — inspect, edit, publish"
    >
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <Select
            label="Company"
            value={selectedCompanyId}
            onChange={setSelectedCompanyId}
            options={[
              { value: '', label: 'Select a company…' },
              ...companies.map((c) => ({ value: c.id, label: c.name })),
            ]}
            placeholder="Select a company…"
          />
          {selectedCompanyId && (
            <Button
              onClick={() => loadPolicies(selectedCompanyId)}
              disabled={loading}
            >
              {loading ? 'Loading…' : 'Refresh'}
            </Button>
          )}
        </div>
      </Card>

      {!selectedCompanyId && (
        <Card padding="lg" className="text-center py-12">
          <p className="text-[#374151] font-medium">Select a company to view policies</p>
          <p className="text-sm text-[#6b7280] mt-1">
            Choose a company from the dropdown above to see source documents, normalized policies, versions, and published state.
          </p>
        </Card>
      )}

      {selectedCompanyId && error && (
        <Card padding="lg" className="mb-4 border-red-200 bg-red-50">
          <p className="text-red-700 text-sm">{error}</p>
        </Card>
      )}

      {selectedCompanyId && !error && data && (
        <>
          <Card padding="lg" className="mb-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-[#0b2b43]">{companyName}</h2>
                <p className="text-sm text-[#6b7280] mt-0.5">
                  Source documents: {sourceDocCount} · Policies: {policies.length}
                </p>
              </div>
              <Link to={`${buildRoute('hrPolicy')}?adminCompanyId=${encodeURIComponent(selectedCompanyId)}`}>
                <Button variant="outline">Open policy workspace</Button>
              </Link>
            </div>
          </Card>

          <Card padding="lg">
            <div className="text-sm text-[#6b7280] mb-2">Policies ({policies.length})</div>
            {policies.length === 0 ? (
              <div className="py-10 text-center text-[#6b7280]">
                <p className="font-medium">No policies for this company</p>
                <p className="text-xs mt-1">Upload and normalize policy documents in the policy workspace to create policies.</p>
                <Link to={`${buildRoute('hrPolicy')}?adminCompanyId=${encodeURIComponent(selectedCompanyId)}`}>
                  <Button variant="outline" className="mt-3">Open policy workspace</Button>
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280]">
                      <th className="py-2 pr-2">Policy title</th>
                      <th className="py-2 pr-2">Latest version</th>
                      <th className="py-2 pr-2">Published</th>
                      <th className="py-2 pr-2">Source docs</th>
                      <th className="py-2 pr-2">Versions</th>
                      <th className="py-2 pr-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {policies.map((p) => (
                      <tr key={p.policy_id} className="border-b border-[#e2e8f0] hover:bg-[#f8fafc]">
                        <td className="py-2 pr-2 font-medium text-[#0b2b43]">{p.title || '—'}</td>
                        <td className="py-2 pr-2">
                          <Badge variant={VERSION_STATUS_VARIANTS[p.latest_version_status ?? ''] || 'neutral'} size="sm">
                            {p.latest_version_number ?? '—'} ({VERSION_STATUS_LABELS[p.latest_version_status ?? ''] ?? p.latest_version_status ?? '—'})
                          </Badge>
                        </td>
                        <td className="py-2 pr-2">
                          {p.published_version_id ? (
                            <span className="text-green-700">Yes · {formatDate(p.published_at)}</span>
                          ) : (
                            <span className="text-[#6b7280]">No</span>
                          )}
                        </td>
                        <td className="py-2 pr-2">{sourceDocCount}</td>
                        <td className="py-2 pr-2">{p.version_count}</td>
                        <td className="py-2 pr-2">
                          <div className="flex flex-wrap gap-1">
                            <Button size="sm" variant="outline" onClick={() => openInspect(p.policy_id)}>
                              Inspect
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => openEdit(p.policy_id)}>
                              Edit
                            </Button>
                            <Link to={`${buildRoute('hrPolicy')}?adminCompanyId=${encodeURIComponent(selectedCompanyId)}`}>
                              <Button size="sm" variant="outline">Open</Button>
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      {/* Inspect modal */}
      {inspectPolicyId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={closeInspect}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="p-4 border-b border-[#e2e8f0] flex justify-between items-center">
              <h3 className="text-lg font-semibold text-[#0b2b43]">Policy details</h3>
              <Button size="sm" variant="ghost" onClick={closeInspect}>Close</Button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              {inspectDetail ? (
                <div className="space-y-4 text-sm">
                  <div>
                    <span className="text-[#6b7280]">Company:</span>{' '}
                    <span className="font-medium">{inspectDetail.company_name ?? inspectDetail.company_id}</span>
                  </div>
                  <div>
                    <span className="text-[#6b7280]">Title:</span>{' '}
                    {inspectDetail.title ?? '—'}
                  </div>
                  <div>
                    <span className="text-[#6b7280]">Source documents:</span> {inspectDetail.source_document_count}
                  </div>
                  <div>
                    <span className="text-[#6b7280]">Published version:</span>{' '}
                    {inspectDetail.published_version_id
                      ? `${formatDate(inspectDetail.published_at)} (version id: ${inspectDetail.published_version_id.slice(0, 8)}…)`
                      : 'None'}
                  </div>
                  <div>
                    <p className="text-[#6b7280] mb-1">Versions ({inspectDetail.versions?.length ?? 0})</p>
                    <ul className="list-disc list-inside space-y-1">
                      {(inspectDetail.versions as AdminPolicyVersion[] | undefined)?.map((v) => (
                        <li key={v.id}>
                          <span className="mr-1">
                            <Badge variant={VERSION_STATUS_VARIANTS[v.status] || 'neutral'} size="sm">
                              {v.version_number} · {VERSION_STATUS_LABELS[v.status] ?? v.status}
                            </Badge>
                          </span>
                          {v.id === inspectDetail.published_version_id && ' (published)'}
                          {v.status !== 'published' && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="ml-2"
                              onClick={() => publishVersion(inspectDetail.id, v.id)}
                            >
                              Publish
                            </Button>
                          )}
                        </li>
                      ))}
                    </ul>
                    {inspectDetail.published_version_id && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="mt-2"
                        onClick={() => unpublishPolicy(inspectDetail.id)}
                      >
                        Unpublish
                      </Button>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-[#6b7280]">Loading…</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit modal */}
      {editPolicyId && editDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={closeEdit}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-[#0b2b43] mb-4">Edit policy metadata</h3>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-[#6b7280] mb-1">Title</label>
                <input
                  type="text"
                  className="w-full border border-[#e2e8f0] rounded px-2 py-1.5"
                  value={editForm.title}
                  onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-[#6b7280] mb-1">Version label</label>
                <input
                  type="text"
                  className="w-full border border-[#e2e8f0] rounded px-2 py-1.5"
                  value={editForm.version}
                  onChange={(e) => setEditForm((f) => ({ ...f, version: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-[#6b7280] mb-1">Effective date</label>
                <input
                  type="text"
                  className="w-full border border-[#e2e8f0] rounded px-2 py-1.5"
                  placeholder="YYYY-MM-DD"
                  value={editForm.effective_date}
                  onChange={(e) => setEditForm((f) => ({ ...f, effective_date: e.target.value }))}
                />
              </div>
              <div className="pt-2">
                <p className="text-[#6b7280] mb-1">Publish</p>
                {(editDetail.versions as AdminPolicyVersion[] | undefined)?.map((v) => (
                  <div key={v.id} className="flex items-center gap-2 py-1">
                    <Badge variant={VERSION_STATUS_VARIANTS[v.status] || 'neutral'} size="sm">
                      v{v.version_number} · {VERSION_STATUS_LABELS[v.status] ?? v.status}
                    </Badge>
                    {v.id === editDetail.published_version_id && <span className="text-green-600">Current</span>}
                    {v.status !== 'published' && (
                      <Button size="sm" variant="outline" onClick={() => publishVersion(editDetail.id, v.id)}>
                        Publish this
                      </Button>
                    )}
                  </div>
                ))}
                {editDetail.published_version_id && (
                  <Button size="sm" variant="outline" className="mt-2" onClick={() => unpublishPolicy(editDetail.id)}>
                    Unpublish
                  </Button>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <Button variant="outline" onClick={closeEdit}>Cancel</Button>
              <Button onClick={saveEdit} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
            </div>
          </div>
        </div>
      )}

      <Card padding="lg" className="mt-4">
        <h3 className="text-sm font-medium text-[#374151] mb-2">Policy assistance</h3>
        <ul className="text-sm text-[#4b5563] space-y-1 list-disc list-inside">
          <li><strong>Company filter</strong> — Select a company first to see its policies, source docs, and versions.</li>
          <li><strong>Inspect</strong> — View policy detail, versions, and published state; publish or unpublish from here.</li>
          <li><strong>Edit</strong> — Change policy title, version label, effective date; publish/unpublish a version.</li>
          <li><strong>Open</strong> — Opens the HR policy workspace for this company (upload, normalize, review).</li>
        </ul>
        <div className="mt-3 flex gap-4">
          <Link to={buildRoute('adminCompanies')} className="text-sm font-medium text-[#0b2b43] hover:underline">Companies →</Link>
          <Link to={buildRoute('adminPeople')} className="text-sm font-medium text-[#0b2b43] hover:underline">People (view-as) →</Link>
        </div>
      </Card>
    </AdminLayout>
  );
};
