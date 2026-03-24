import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Card, Button, Badge } from '../../../components/antigravity';
import { AdminLayout } from '../../../pages/admin/AdminLayout';
import { adminAPI, policyConfigMatrixAPI } from '../../../api/client';
import type { AdminCompany, AdminPoliciesByCompany, AdminPolicyDetail, AdminPolicyTemplate, AdminPolicyVersion } from '../../../types';
import type { PolicyConfigWorkingPayload } from '../../policy-config/types';
import { usePolicyConfigWorkspace } from '../../policy-config/usePolicyConfigWorkspace';
import { validatePolicyConfigForPublish } from '../../policy-config/benefitRowValidation';
import { PolicyWorkspaceIntroCard } from './PolicyWorkspaceIntroCard';
import { POLICY_WORKSPACE_SUBTITLE, POLICY_WORKSPACE_TITLE } from './PolicyWorkspaceHeader';
import { PolicyWorkspaceControls } from './PolicyWorkspaceControls';
import { PolicyWorkspaceSummaryTiles } from './PolicyWorkspaceSummaryTiles';
import { PolicyThemeAccordionList } from './PolicyThemeAccordionList';
import { PolicySourceHistorySection } from './PolicySourceHistorySection';
import {
  deriveSourceModeLabel,
  deriveWorkspaceAggregate,
  unpublishedChangesLabel,
} from './policyWorkspaceModel';
import { buildRoute } from '../../../navigation/routes';

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
  if (!val) return '-';
  try {
    return new Date(val).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return String(val);
  }
}

function asWorkingPayload(raw: unknown): PolicyConfigWorkingPayload | null {
  if (!raw || typeof raw !== 'object') return null;
  return raw as PolicyConfigWorkingPayload;
}

export const PolicyWorkspacePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>('');
  const pcw = usePolicyConfigWorkspace({ mode: 'admin', adminCompanyId: selectedCompanyId || undefined });
  const [data, setData] = useState<AdminPoliciesByCompany | null>(null);
  const [loading, setLoading] = useState(false);
  const [draftActionLoading, setDraftActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inspectPolicyId, setInspectPolicyId] = useState<string | null>(null);
  const [inspectDetail, setInspectDetail] = useState<AdminPolicyDetail | null>(null);
  const [editPolicyId, setEditPolicyId] = useState<string | null>(null);
  const [editDetail, setEditDetail] = useState<AdminPolicyDetail | null>(null);
  const [editForm, setEditForm] = useState<{ title: string; version: string; effective_date: string }>({
    title: '',
    version: '',
    effective_date: '',
  });
  const [policyDocSaving, setPolicyDocSaving] = useState(false);
  const [templates, setTemplates] = useState<AdminPolicyTemplate[]>([]);
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [publishedOpen, setPublishedOpen] = useState(false);
  const [publishedPayload, setPublishedPayload] = useState<PolicyConfigWorkingPayload | null>(null);
  const [publishedLoading, setPublishedLoading] = useState(false);
  const [publishModalOpen, setPublishModalOpen] = useState(false);
  const [publishEffectiveDate, setPublishEffectiveDate] = useState('');
  const [publishModalError, setPublishModalError] = useState<string | null>(null);

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
      const msg =
        e && typeof e === 'object' && 'response' in e && typeof (e as { response?: { data?: { detail?: string } } }).response?.data?.detail === 'string'
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

  const loadTemplates = useCallback(async () => {
    try {
      const res = await adminAPI.listAdminPolicyTemplates();
      setTemplates(res.templates ?? []);
    } catch {
      setTemplates([]);
    }
  }, []);

  useEffect(() => {
    loadTemplates().catch(() => undefined);
  }, [loadTemplates]);

  useEffect(() => {
    const cid = searchParams.get('company_id')?.trim();
    if (cid) setSelectedCompanyId(cid);
  }, [searchParams]);

  useEffect(() => {
    if (selectedCompanyId) {
      loadPolicies(selectedCompanyId).catch(() => undefined);
    } else {
      setData(null);
      setError(null);
    }
  }, [selectedCompanyId, loadPolicies]);

  const refreshAll = useCallback(() => {
    if (!selectedCompanyId) return;
    loadPolicies(selectedCompanyId).catch(() => undefined);
    pcw.load().catch(() => undefined);
  }, [selectedCompanyId, loadPolicies, pcw.load]);

  const applyDefaultTemplate = useCallback(async () => {
    if (!selectedCompanyId) return;
    setApplyingTemplate(true);
    try {
      await adminAPI.applyDefaultTemplateToCompany(selectedCompanyId);
      await loadPolicies(selectedCompanyId);
    } catch (e: unknown) {
      const msg =
        e && typeof e === 'object' && 'response' in e && typeof (e as { response?: { data?: { detail?: string } } }).response?.data?.detail === 'string'
          ? (e as { response: { data: { detail: string } } }).response.data.detail
          : 'Failed to apply template';
      setError(msg);
    } finally {
      setApplyingTemplate(false);
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
    setPolicyDocSaving(false);
  }, []);

  const saveEdit = useCallback(async () => {
    if (!editPolicyId || !editDetail) return;
    setPolicyDocSaving(true);
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
      setPolicyDocSaving(false);
    }
  }, [editPolicyId, editDetail, editForm, selectedCompanyId, loadPolicies, closeEdit]);

  const publishVersion = useCallback(
    async (policyId: string, versionId: string) => {
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
        /* keep UI */
      }
    },
    [inspectPolicyId, editPolicyId, selectedCompanyId, loadPolicies]
  );

  const unpublishPolicy = useCallback(
    async (policyId: string) => {
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
        /* keep UI */
      }
    },
    [inspectPolicyId, editPolicyId, selectedCompanyId, loadPolicies]
  );

  const createDraftFromPublished = useCallback(async () => {
    if (!selectedCompanyId) return;
    setDraftActionLoading(true);
    pcw.setError(null);
    try {
      await pcw.startEditing();
    } finally {
      setDraftActionLoading(false);
    }
  }, [selectedCompanyId, pcw.startEditing, pcw.setError]);

  const openPublishModal = useCallback(() => {
    setPublishModalError(null);
    const ed = (pcw.payload?.effective_date ?? '').toString().trim().slice(0, 10);
    setPublishEffectiveDate(ed);
    setPublishModalOpen(true);
  }, [pcw.payload?.effective_date]);

  const closePublishModal = useCallback(() => {
    setPublishModalOpen(false);
    setPublishModalError(null);
  }, []);

  const confirmPublishMatrix = useCallback(async () => {
    setPublishModalError(null);
    const ed = publishEffectiveDate.trim().slice(0, 10);
    if (!ed) {
      setPublishModalError('Effective date is required.');
      return;
    }
    if (!pcw.payload) return;
    const merged: PolicyConfigWorkingPayload = { ...pcw.payload, effective_date: ed };
    const pubErrors = validatePolicyConfigForPublish(merged);
    if (pubErrors.length) {
      setPublishModalError(pubErrors.map((e) => e.message).join('\n'));
      return;
    }
    const saved = await pcw.saveDraft(merged);
    if (!saved) return;
    const published = await pcw.publish(saved);
    if (published) closePublishModal();
  }, [publishEffectiveDate, pcw.saveDraft, pcw.publish, closePublishModal]);

  const openPublishedPreview = useCallback(async () => {
    if (!selectedCompanyId) return;
    setPublishedOpen(true);
    setPublishedPayload(null);
    setPublishedLoading(true);
    try {
      const raw = await policyConfigMatrixAPI.adminPublished(selectedCompanyId);
      setPublishedPayload(asWorkingPayload(raw));
    } catch {
      setPublishedPayload(null);
    } finally {
      setPublishedLoading(false);
    }
  }, [selectedCompanyId]);

  const closePublished = useCallback(() => {
    setPublishedOpen(false);
    setPublishedPayload(null);
  }, []);

  const companyName = data?.company_name ?? companies.find((c) => c.id === selectedCompanyId)?.name ?? '';
  const sourceDocCount = data?.source_document_count ?? 0;
  const matrixPayload = pcw.payload;
  const aggregate = deriveWorkspaceAggregate(matrixPayload);
  const sourceModeLabel = deriveSourceModeLabel(sourceDocCount, matrixPayload);
  const matrixInspectOnly = Boolean(matrixPayload && matrixPayload.editable === false);
  const policyConfigHref = `${buildRoute('adminPolicyConfig')}?companyId=${encodeURIComponent(selectedCompanyId)}`;
  const hrPolicyHref = `${buildRoute('hrPolicy')}?adminCompanyId=${encodeURIComponent(selectedCompanyId)}`;

  return (
    <AdminLayout title={POLICY_WORKSPACE_TITLE} subtitle={POLICY_WORKSPACE_SUBTITLE}>
      <PolicyWorkspaceIntroCard />

      {publishModalOpen && (
        <div
          className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4"
          onClick={closePublishModal}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-md w-full p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-[#0b2b43] mb-2">Publish structured baseline?</h3>
            <p className="text-sm text-[#64748b] mb-4">
              Publishing replaces the current published version for this company. Employees and budget checks will use
              the new baseline. Draft version id:{' '}
              <span className="font-mono text-xs">{matrixPayload?.policy_version?.slice(0, 10) ?? '—'}…</span>
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-[#374151] mb-1">Effective date (required)</label>
              <input
                type="date"
                className="w-full border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm"
                value={publishEffectiveDate}
                onChange={(e) => setPublishEffectiveDate(e.target.value)}
              />
            </div>
            {publishModalError ? (
              <p className="text-sm text-[#7a2a2a] mb-3 whitespace-pre-wrap">{publishModalError}</p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={closePublishModal} disabled={pcw.publishing}>
                Cancel
              </Button>
              <Button onClick={() => confirmPublishMatrix().catch(() => undefined)} disabled={pcw.publishing || pcw.saving}>
                {pcw.publishing || pcw.saving ? 'Working…' : 'Confirm publish'}
              </Button>
            </div>
          </div>
        </div>
      )}

      <PolicyWorkspaceControls
        companies={companies}
        selectedCompanyId={selectedCompanyId}
        onCompanyChange={setSelectedCompanyId}
        onRefresh={refreshAll}
        loading={loading}
        matrixPayload={matrixPayload}
        matrixLoading={pcw.loading}
        sourceModeLabel={sourceModeLabel}
        onCreateDraftFromPublished={createDraftFromPublished}
        draftActionLoading={draftActionLoading}
        onViewPublished={openPublishedPreview}
        onSaveDraft={() => pcw.saveDraft().catch(() => undefined)}
        saveDraftDisabled={
          !matrixPayload?.policy_version || matrixPayload.editable === false || pcw.saving || pcw.loading
        }
        onPublishDraft={openPublishModal}
        publishDisabled={
          !matrixPayload?.policy_version || matrixPayload.editable === false || pcw.publishing || pcw.loading
        }
        savingDraft={pcw.saving}
        publishingDraft={pcw.publishing}
        policyConfigHref={policyConfigHref}
        hrPolicyHref={hrPolicyHref}
      />

      {!selectedCompanyId && (
        <Card padding="lg" className="text-center py-12 mt-4">
          <p className="text-[#374151] font-medium">Select a company</p>
          <p className="text-sm text-[#6b7280] mt-1">
            Choose a company to review and edit the structured relocation baseline, then manage sources and versions below.
          </p>
        </Card>
      )}

      {selectedCompanyId && pcw.error ? (
        <Card padding="lg" className="mb-4 border-amber-200 bg-amber-50">
          <p className="text-amber-900 text-sm whitespace-pre-wrap">{pcw.error}</p>
        </Card>
      ) : null}

      {selectedCompanyId ? (
        <>
          <PolicyWorkspaceSummaryTiles
            aggregate={aggregate}
            sourceMode={sourceModeLabel}
            unpublishedLabel={unpublishedChangesLabel(matrixPayload)}
          />

          <Card padding="lg" className="mb-6 border-[#e2e8f0]">
            <PolicyThemeAccordionList
              categories={matrixPayload?.categories}
              policyEditorHref={policyConfigHref}
              assignmentTypesSupported={matrixPayload?.assignment_types_supported}
              familyStatusesSupported={matrixPayload?.family_statuses_supported}
              basePayload={matrixPayload}
              saveDraft={pcw.saveDraft}
              onRequestCreateDraft={createDraftFromPublished}
              setWorkspaceError={pcw.setError}
              serverErrorsByBenefitKey={pcw.serverErrorsByBenefitKey}
              matrixInspectOnly={matrixInspectOnly}
            />
            <div className="mt-4 pt-4 border-t border-[#f1f5f9] flex flex-wrap gap-2">
              <Link
                to={policyConfigHref}
                className="inline-flex items-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 border-2 border-[#0b2b43] text-[#0b2b43] hover:bg-[#e6f2f4] focus:ring-[#0b2b43] px-4 py-2 text-base"
              >
                Edit structured baseline
              </Link>
              <p className="text-xs text-[#64748b] w-full sm:w-auto sm:ml-2 self-center">
                Use row drawers for most edits; open Compensation &amp; Allowance for bulk work on the same company.
              </p>
            </div>
          </Card>
        </>
      ) : null}

      <PolicySourceHistorySection
        selectedCompanyId={selectedCompanyId}
        companyName={companyName}
        data={data}
        loading={loading}
        error={error}
        sourceDocCount={sourceDocCount}
        latestSourceDocumentTitle={data?.latest_source_document_title}
        sourceModeLabel={sourceModeLabel}
        policyConfigHref={policyConfigHref}
        templates={templates}
        applyingTemplate={applyingTemplate}
        onApplyDefaultTemplate={applyDefaultTemplate}
        onInspect={openInspect}
        onEdit={openEdit}
      />

      {publishedOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={closePublished}>
          <div
            className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-[#e2e8f0] flex justify-between items-center gap-2">
              <h3 className="text-lg font-semibold text-[#0b2b43]">Published structured baseline</h3>
              <Button size="sm" variant="ghost" onClick={closePublished}>
                Close
              </Button>
            </div>
            <div className="p-4 overflow-y-auto flex-1 text-sm">
              {publishedLoading ? (
                <p className="text-[#64748b]">Loading…</p>
              ) : publishedPayload?.status === 'none' ? (
                <p className="text-[#64748b]">No published structured baseline for this company yet.</p>
              ) : !publishedPayload ? (
                <p className="text-[#64748b]">Could not load the published baseline.</p>
              ) : (
                <>
                  <p className="text-[#64748b] mb-3">
                    Read-only snapshot of what employees and budget checks use after publish (version{' '}
                    {publishedPayload.version_number ?? '—'}, effective {publishedPayload.effective_date ?? '—'}).
                  </p>
                  <PolicyThemeAccordionList
                    categories={publishedPayload.categories}
                    policyEditorHref={policyConfigHref}
                    readOnly
                    assignmentTypesSupported={publishedPayload.assignment_types_supported}
                    familyStatusesSupported={publishedPayload.family_statuses_supported}
                    basePayload={publishedPayload}
                    saveDraft={async () => null}
                    onRequestCreateDraft={async () => {}}
                    setWorkspaceError={() => {}}
                    serverErrorsByBenefitKey={{}}
                    matrixInspectOnly
                  />
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {inspectPolicyId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={closeInspect}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="p-4 border-b border-[#e2e8f0] flex justify-between items-center">
              <h3 className="text-lg font-semibold text-[#0b2b43]">Policy details</h3>
              <Button size="sm" variant="ghost" onClick={closeInspect}>
                Close
              </Button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              {inspectDetail ? (
                <div className="space-y-4 text-sm">
                  <div>
                    <span className="text-[#6b7280]">Company:</span>{' '}
                    <span className="font-medium">{inspectDetail.company_name ?? inspectDetail.company_id}</span>
                  </div>
                  <div>
                    <span className="text-[#6b7280]">Title:</span> {inspectDetail.title ?? '-'}
                  </div>
                  <div>
                    <span className="text-[#6b7280]">Source:</span>{' '}
                    {(inspectDetail.template_source as string) === 'default_platform_template' ? 'Default template' : 'Custom uploaded'}
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
                            <Button size="sm" variant="ghost" className="ml-2" onClick={() => publishVersion(inspectDetail.id, v.id)}>
                              Publish
                            </Button>
                          )}
                        </li>
                      ))}
                    </ul>
                    {inspectDetail.published_version_id && (
                      <Button size="sm" variant="outline" className="mt-2" onClick={() => unpublishPolicy(inspectDetail.id)}>
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
              <Button variant="outline" onClick={closeEdit}>
                Cancel
              </Button>
              <Button onClick={saveEdit} disabled={policyDocSaving}>
                {policyDocSaving ? 'Saving…' : 'Save'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
};
