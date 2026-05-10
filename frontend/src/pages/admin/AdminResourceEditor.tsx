import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminResourcesAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';
import { InternalThreadPanel } from '../../components/admin/collaboration/InternalThreadPanel';

const AUDIENCE_OPTIONS = ['all', 'couple', 'family', 'single', 'spouse_job_seeker', 'with_children'];
const RESOURCE_TYPES = ['checklist_item', 'event_source', 'guide', 'official_link', 'place', 'provider', 'tip'];
const BUDGET_OPTIONS = ['high', 'low', 'mid'];

export const AdminResourceEditor: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = id === 'new' || !id;
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [categories, setCategories] = useState<{ id: string; key: string; label: string }[]>([]);
  const [tags, setTags] = useState<{ id: string; key: string; label: string; tag_group?: string }[]>([]);
  const [sources, setSources] = useState<{ id: string; source_name: string }[]>([]);
  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [approveNotes, setApproveNotes] = useState('');
  const [auditEntries, setAuditEntries] = useState<Array<{ action_type: string; created_at: string; performed_by_user_id?: string; previous_status?: string; new_status?: string; change_summary?: string }>>([]);
  const [form, setForm] = useState<Record<string, unknown>>({
    country_code: 'NO',
    title: '',
    summary: '',
    body: '',
    resource_type: 'guide',
    audience_type: 'all',
    budget_tier: '',
    is_family_friendly: false,
    is_featured: false,
    internal_notes: '',
    review_notes: '',
  });

  const loadTaxonomy = async () => {
    try {
      const [catRes, tagRes, srcRes] = await Promise.all([
        adminResourcesAPI.listCategories(),
        adminResourcesAPI.listTags(),
        adminResourcesAPI.listSources(),
      ]);
      setCategories(catRes.categories || []);
      setTags(tagRes.tags || []);
      setSources(srcRes.sources || []);
    } catch {
      //
    }
  };

  const load = async () => {
    if (isNew) return;
    setLoading(true);
    try {
      const r = await adminResourcesAPI.getResource(id!) as Record<string, unknown>;
      setForm({
        ...r,
        tag_ids: (r.tag_ids as string[]) || [],
      });
    } catch {
      setForm({});
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTaxonomy();
  }, []);

  useEffect(() => {
    load();
  }, [id]);

  const loadAudit = async () => {
    if (isNew || !id) return;
    try {
      const res = await adminResourcesAPI.getResourceAudit(id!, 20) as { entries?: Array<{ action_type: string; created_at: string; performed_by_user_id?: string; previous_status?: string; new_status?: string; change_summary?: string }> };
      setAuditEntries(res.entries || []);
    } catch {
      setAuditEntries([]);
    }
  };

  useEffect(() => {
    if (!isNew && id) loadAudit();
  }, [id, isNew]);

  const update = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  const saveDraft = async () => {
    setSaving(true);
    try {
      const payload = { ...form } as Record<string, unknown>;
      payload.tag_ids = (form.tag_ids as string[]) || [];
      delete payload.id;
      delete payload.created_at;
      delete payload.updated_at;
      delete payload.created_by_user_id;
      delete payload.updated_by_user_id;
      delete payload.reviewed_by_user_id;
      delete payload.published_by_user_id;
      delete payload.reviewed_at;
      delete payload.published_at;
      delete payload.archived_at;
      if (isNew) {
        const created = await adminResourcesAPI.createResource(payload) as { id: string };
        navigate(buildRoute('adminResourcesEdit', { id: created.id }), { replace: true });
      } else {
        await adminResourcesAPI.updateResource(id!, payload);
        load();
      }
    } catch (e) {
      alert((e as Error).message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const workflow = async (action: string, notes?: string) => {
    if (!id || isNew) return;
    setSaving(true);
    try {
      switch (action) {
        case 'submit':
          await adminResourcesAPI.submitForReview(id);
          break;
        case 'approve':
          await adminResourcesAPI.approveResource(id, notes);
          break;
        case 'publish':
          await adminResourcesAPI.publishResource(id);
          break;
        case 'archive':
          await adminResourcesAPI.archiveResource(id);
          break;
        case 'unpublish':
          await adminResourcesAPI.unpublishResource(id);
          break;
        case 'restore':
          await adminResourcesAPI.restoreResource(id);
          break;
        default:
          return;
      }
      load();
      loadAudit();
    } catch (e) {
      alert((e as Error).message || 'Action failed');
    } finally {
      setSaving(false);
    }
  };

  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Resource" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  if (loading && !isNew) {
    return (
      <AdminLayout title="Resource" subtitle="Loading…">
        <div className="py-8 text-center text-slate-500">Loading…</div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout
      title={isNew ? 'New Resource' : (form.title as string) || 'Edit Resource'}
      subtitle={
        isNew
          ? 'Create a new country resource'
          : `Status: ${form.status || 'draft'}${form.is_visible_to_end_users ? ' • Visible to end users' : ''}`
      }
    >
      <div className="mb-4 flex gap-2">
        <Link to={buildRoute('adminResources')}>
          <Button variant="secondary">← Back</Button>
        </Link>
        <Button onClick={saveDraft} disabled={saving}>
          {saving ? 'Saving…' : 'Save Draft'}
        </Button>
        {!isNew && (form.status as string) === 'draft' && (
          <Button variant="primary" onClick={() => workflow('submit')} disabled={saving}>
            Submit for Review
          </Button>
        )}
        {!isNew && (form.status as string) === 'in_review' && (
          <Button
            variant="primary"
            onClick={() => setApproveModalOpen(true)}
            disabled={saving}
          >
            Approve
          </Button>
        )}
        {!isNew && (form.status as string) === 'approved' && (
          <Button variant="primary" onClick={() => workflow('publish')} disabled={saving}>
            Publish
          </Button>
        )}
        {!isNew && (form.status as string) === 'published' && (
          <>
            <Button variant="secondary" onClick={() => workflow('unpublish')} disabled={saving}>
              Unpublish
            </Button>
            <Button variant="secondary" onClick={() => workflow('archive')} disabled={saving}>
              Archive
            </Button>
          </>
        )}
        {approveModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setApproveModalOpen(false)}>
            <div className="bg-white rounded-lg shadow-lg p-4 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
              <h4 className="font-semibold mb-2">Approve resource</h4>
              <label className="block text-sm text-slate-600 mb-2">Review notes (optional)</label>
              <textarea
                value={approveNotes}
                onChange={(e) => setApproveNotes(e.target.value)}
                rows={2}
                className="w-full border border-slate-200 rounded px-2 py-1 text-sm mb-4"
              />
              <div className="flex gap-2">
                <Button onClick={() => { workflow('approve', approveNotes || undefined); setApproveModalOpen(false); setApproveNotes(''); }} disabled={saving}>
                  {saving ? 'Approving…' : 'Approve'}
                </Button>
                <Button variant="secondary" onClick={() => { setApproveModalOpen(false); setApproveNotes(''); }}>
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        )}
        {!isNew && (form.status as string) === 'archived' && (
          <Button variant="secondary" onClick={() => workflow('restore')} disabled={saving}>
            Restore
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card padding="lg">
          <h3 className="font-semibold mb-3">Basic</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-slate-600 mb-1">Title *</label>
              <input
                value={(form.title as string) || ''}
                onChange={(e) => update('title', e.target.value)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-sm text-slate-600 mb-1">Country</label>
                <input
                  value={(form.country_code as string) || ''}
                  onChange={(e) => update('country_code', e.target.value.toUpperCase())}
                  className="w-full rounded border border-slate-200 px-3 py-2"
                  placeholder="NO"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-600 mb-1">City</label>
                <input
                  value={(form.city_name as string) || ''}
                  onChange={(e) => update('city_name', e.target.value)}
                  className="w-full rounded border border-slate-200 px-3 py-2"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Category</label>
              <select
                value={(form.category_id as string) || ''}
                onChange={(e) => update('category_id', e.target.value || null)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              >
                <option value="">None</option>
                {[...categories].sort((a, b) => (a.label || a.key).localeCompare(b.label || b.key)).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label} ({c.key})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Resource Type</label>
              <select
                value={(form.resource_type as string) || 'guide'}
                onChange={(e) => update('resource_type', e.target.value)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              >
                {RESOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Audience</label>
              <select
                value={(form.audience_type as string) || 'all'}
                onChange={(e) => update('audience_type', e.target.value)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              >
                {AUDIENCE_OPTIONS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Budget Tier</label>
              <select
                value={(form.budget_tier as string) || ''}
                onChange={(e) => update('budget_tier', e.target.value || null)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              >
                <option value="">None</option>
                {BUDGET_OPTIONS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!!form.is_family_friendly}
                  onChange={(e) => update('is_family_friendly', e.target.checked)}
                />
                <span className="text-sm">Family friendly</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!!form.is_featured}
                  onChange={(e) => update('is_featured', e.target.checked)}
                />
                <span className="text-sm">Featured</span>
              </label>
            </div>
          </div>
        </Card>

        <Card padding="lg">
          <h3 className="font-semibold mb-3">Content</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-slate-600 mb-1">Summary</label>
              <textarea
                value={(form.summary as string) || ''}
                onChange={(e) => update('summary', e.target.value)}
                rows={3}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Body</label>
              <textarea
                value={(form.body as string) || ''}
                onChange={(e) => update('body', e.target.value)}
                rows={5}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">External URL</label>
              <input
                value={(form.external_url as string) || ''}
                onChange={(e) => update('external_url', e.target.value)}
                className="w-full rounded border border-slate-200 px-3 py-2"
                placeholder="https://"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Tags</label>
              <div className="flex flex-wrap gap-2">
                {tags.map((t) => {
                  const ids = (form.tag_ids as string[]) || [];
                  const checked = ids.includes(t.id);
                  return (
                    <label key={t.id} className="flex items-center gap-1 text-sm">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            update('tag_ids', [...ids, t.id]);
                          } else {
                            update('tag_ids', ids.filter((x) => x !== t.id));
                          }
                        }}
                      />
                      {t.label}
                    </label>
                  );
                })}
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Source</label>
              <select
                value={(form.source_id as string) || ''}
                onChange={(e) => update('source_id', e.target.value || null)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              >
                <option value="">None</option>
                {[...sources].sort((a, b) => (a.source_name || '').localeCompare(b.source_name || '')).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.source_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </Card>

        <Card padding="lg" className="lg:col-span-2">
          <h3 className="font-semibold mb-3 text-amber-800">Admin Only (never shown to end users)</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-600 mb-1">Internal Notes</label>
              <textarea
                value={(form.internal_notes as string) || ''}
                onChange={(e) => update('internal_notes', e.target.value)}
                rows={2}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Review Notes</label>
              <textarea
                value={(form.review_notes as string) || ''}
                onChange={(e) => update('review_notes', e.target.value)}
                rows={2}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
          </div>
        </Card>

        {!isNew && (
          <>
            <Card padding="lg" className="lg:col-span-2">
              <h3 className="font-semibold mb-3">Public preview</h3>
              <p className="text-sm text-slate-600 mb-2">
                How this resource will appear to end users (no internal notes or workflow metadata).
              </p>
              <div className="p-4 border border-slate-200 rounded-lg bg-slate-50">
                <div className="font-medium text-[#0b2b43]">{(form.title as string) || 'Untitled'}</div>
                {form.summary ? (
                  <p className="text-sm text-slate-600 mt-1">{String(form.summary)}</p>
                ) : null}
                {form.trust_tier ? (
                  <span className="inline-block mt-2 text-xs px-1.5 py-0.5 rounded bg-slate-200">
                    {String(form.trust_tier)}
                  </span>
                ) : null}
                {form.external_url ? (
                  <a
                    href={String(form.external_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-blue-600 mt-2 inline-block"
                  >
                    Visit →
                  </a>
                ) : null}
              </div>
            </Card>

            <Card padding="lg" className="lg:col-span-2">
              <InternalThreadPanel
                targetType="live_resource"
                targetId={id}
                title="Internal discussion"
              />
            </Card>
            <Card padding="lg" className="lg:col-span-2">
              <h3 className="font-semibold mb-3">Audit log</h3>
              <div className="space-y-1 text-sm max-h-48 overflow-y-auto">
                {auditEntries.length === 0 && (
                  <p className="text-slate-500">No audit entries yet.</p>
                )}
                {auditEntries.map((entry, i) => (
                  <div key={i} className="flex flex-wrap gap-2 py-1 border-b border-slate-100 last:border-0">
                    <span className="font-medium">{entry.action_type}</span>
                    {entry.previous_status && entry.new_status && (
                      <span className="text-slate-500">
                        {entry.previous_status} → {entry.new_status}
                      </span>
                    )}
                    {entry.change_summary && (
                      <span className="text-slate-500 truncate max-w-xs">{entry.change_summary}</span>
                    )}
                    <span className="text-slate-400 text-xs">
                      {entry.created_at ? new Date(entry.created_at).toLocaleString() : ''}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </>
        )}
      </div>
    </AdminLayout>
  );
};
