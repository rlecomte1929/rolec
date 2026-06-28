import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Input } from '../../components/antigravity/Input';
import { Checkbox } from '../../components/antigravity/Checkbox';
import { Card, Button } from '../../components/antigravity';
import { adminResourcesAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';
import { InternalThreadPanel } from '../../components/admin/collaboration/InternalThreadPanel';
import { AdminLayout } from './AdminLayout';

const EVENT_TYPES = ['cinema', 'concert', 'family_activity', 'festival', 'museum', 'networking', 'sports', 'theater'];

export const AdminEventEditor: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = id === 'new' || !id;
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [sources, setSources] = useState<{ id: string; source_name: string }[]>([]);
  const [form, setForm] = useState<Record<string, unknown>>({
    country_code: 'NO',
    city_name: '',
    title: '',
    description: '',
    event_type: 'cinema',
    is_free: false,
    is_family_friendly: false,
    internal_notes: '',
  });

  const loadSources = async () => {
    try {
      const res = await adminResourcesAPI.listSources();
      setSources((res.sources || []) as { id: string; source_name: string }[]);
    } catch {
      //
    }
  };

  const load = async () => {
    if (isNew) return;
    setLoading(true);
    try {
      const e = (await adminResourcesAPI.getEvent(id)) as Record<string, unknown>;
      setForm(e);
    } catch {
      setForm({});
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSources();
  }, []);

  useEffect(() => {
    void load();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const update = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  const toISO = (d: Date) => d.toISOString().slice(0, 16);

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form };
      delete payload.id;
      delete payload.created_at;
      delete payload.updated_at;
      if (isNew) {
        const created = (await adminResourcesAPI.createEvent(payload)) as { id: string };
        navigate(buildRoute('adminEventsEdit', { id: created.id }), { replace: true });
      } else {
        await adminResourcesAPI.updateEvent(id, payload);
      }
    } catch (e) {
      alert((e as Error).message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [approveNotes, setApproveNotes] = useState('');
  const [auditEntries, setAuditEntries] = useState<Array<{ action_type: string; created_at: string; previous_status?: string; new_status?: string; change_summary?: string }>>([]);

  const loadAudit = async () => {
    if (isNew || !id) return;
    try {
      const res = await adminResourcesAPI.getEventAudit(id, 20) as { entries?: Array<{ action_type: string; created_at: string; previous_status?: string; new_status?: string; change_summary?: string }> };
      setAuditEntries(res.entries || []);
    } catch {
      setAuditEntries([]);
    }
  };

  useEffect(() => {
    if (!isNew && id) void loadAudit();
  }, [id, isNew]); // eslint-disable-line react-hooks/exhaustive-deps

  const workflow = async (action: string, notes?: string) => {
    if (!id || isNew) return;
    setSaving(true);
    try {
      switch (action) {
        case 'submit':
          await adminResourcesAPI.submitEventForReview(id);
          break;
        case 'approve':
          await adminResourcesAPI.approveEvent(id, notes);
          break;
        case 'publish':
          await adminResourcesAPI.publishEvent(id);
          break;
        case 'unpublish':
          await adminResourcesAPI.unpublishEvent(id);
          break;
        case 'archive':
          await adminResourcesAPI.archiveEvent(id);
          break;
        case 'restore':
          await adminResourcesAPI.restoreEvent(id);
          break;
        default:
          return;
      }
      void load();
      void loadAudit();
    } catch (e) {
      alert((e as Error).message || 'Action failed');
    } finally {
      setSaving(false);
    }
  };

  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Event" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  if (loading && !isNew) {
    return (
      <AdminLayout title="Event" subtitle="Loading…">
        <div className="py-8 text-center text-slate-500">Loading…</div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout
      title={isNew ? 'New Event' : (form.title as string) || 'Edit Event'}
      subtitle={isNew ? 'Create a new event' : `Status: ${(form.status as string | undefined) || 'draft'}`}
    >
      <div className="mb-4 flex gap-2">
        <Link to={buildRoute('adminEvents')}>
          <Button variant="secondary">← Back</Button>
        </Link>
        <Button onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
        {!isNew && (form.status as string) === 'draft' && (
          <Button variant="primary" onClick={() => workflow('submit')} disabled={saving}>
            Submit for Review
          </Button>
        )}
        {!isNew && (form.status as string) === 'in_review' && (
          <Button variant="primary" onClick={() => setApproveModalOpen(true)} disabled={saving}>
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
        {!isNew && (form.status as string) === 'archived' && (
          <Button variant="secondary" onClick={() => workflow('restore')} disabled={saving}>
            Restore
          </Button>
        )}
      </div>

      {approveModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={(e) => { if (e.target === e.currentTarget) setApproveModalOpen(false); }}
          onKeyDown={(e) => { if (e.key === 'Escape') setApproveModalOpen(false); }}
          role="button"
          tabIndex={-1}
          aria-label="Close approve dialog"
        >
          <div className="bg-white rounded-lg shadow-lg p-4 max-w-md w-full mx-4">
            <h4 className="font-semibold mb-2">Approve event</h4>
            <label htmlFor="evt-review-notes-optional" className="block text-sm text-slate-600 mb-2">Review notes (optional)</label>
            <textarea id="evt-review-notes-optional" value={approveNotes} onChange={(e) => setApproveNotes(e.target.value)} rows={2} className="w-full border border-slate-200 rounded px-2 py-1 text-sm mb-4" />
            <div className="flex gap-2">
              <Button onClick={() => { void workflow('approve', approveNotes || undefined); setApproveModalOpen(false); setApproveNotes(''); }} disabled={saving}>
                {saving ? 'Approving…' : 'Approve'}
              </Button>
              <Button variant="secondary" onClick={() => { setApproveModalOpen(false); setApproveNotes(''); }}>Cancel</Button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card padding="lg">
          <h3 className="font-semibold mb-3">Basic</h3>
          <div className="space-y-3">
            <div>
              <label htmlFor="evt-title" className="block text-sm text-slate-600 mb-1">Title *</label>
              <Input unstyled
                id="evt-title"
                value={(form.title as string) || ''}
                onChange={(v) => update('title', v)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor="evt-country" className="block text-sm text-slate-600 mb-1">Country</label>
                <Input unstyled
                  id="evt-country"
                  value={(form.country_code as string) || ''}
                  onChange={(v) => update('country_code', v.toUpperCase())}
                  className="w-full rounded border border-slate-200 px-3 py-2"
                />
              </div>
              <div>
                <label htmlFor="evt-city" className="block text-sm text-slate-600 mb-1">City</label>
                <Input unstyled
                  id="evt-city"
                  value={(form.city_name as string) || ''}
                  onChange={(v) => update('city_name', v)}
                  className="w-full rounded border border-slate-200 px-3 py-2"
                />
              </div>
            </div>
            <div>
              <label htmlFor="evt-event-type" className="block text-sm text-slate-600 mb-1">Event Type</label>
              <select
                id="evt-event-type"
                value={(form.event_type as string) || 'cinema'}
                onChange={(e) => update('event_type', e.target.value)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              >
                {EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="evt-description" className="block text-sm text-slate-600 mb-1">Description</label>
              <textarea
                id="evt-description"
                value={(form.description as string) || ''}
                onChange={(e) => update('description', e.target.value)}
                rows={3}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div>
              <label htmlFor="evt-venue" className="block text-sm text-slate-600 mb-1">Venue</label>
              <Input unstyled
                id="evt-venue"
                value={(form.venue_name as string) || ''}
                onChange={(v) => update('venue_name', v)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div>
              <label htmlFor="evt-address" className="block text-sm text-slate-600 mb-1">Address</label>
              <Input unstyled
                id="evt-address"
                value={(form.address as string) || ''}
                onChange={(v) => update('address', v)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor="evt-start-iso" className="block text-sm text-slate-600 mb-1">Start (ISO)</label>
                <Input unstyled
                  id="evt-start-iso"
                  type="datetime-local"
                  value={
                    form.start_datetime
                      ? toISO(new Date(form.start_datetime as string))
                      : toISO(new Date())
                  }
                  onChange={(v) => update('start_datetime', v ? new Date(v).toISOString() : null)}
                  className="w-full rounded border border-slate-200 px-3 py-2"
                />
              </div>
              <div>
                <label htmlFor="evt-end-iso" className="block text-sm text-slate-600 mb-1">End (ISO)</label>
                <Input unstyled
                  id="evt-end-iso"
                  type="datetime-local"
                  value={
                    form.end_datetime
                      ? toISO(new Date(form.end_datetime as string))
                      : ''
                  }
                  onChange={(v) => update('end_datetime', v ? new Date(v).toISOString() : null)}
                  className="w-full rounded border border-slate-200 px-3 py-2"
                />
              </div>
            </div>
            <div>
              <span className="block text-sm text-slate-600 mb-1">Price / Free</span>
              <div className="flex gap-4 items-center">
                <label htmlFor="evt-free" className="flex items-center gap-2">
                  <Checkbox
                    id="evt-free"
                    checked={!!form.is_free}
                    onChange={(e) => update('is_free', e.target.checked)}
                  />
                  <span className="text-sm">Free</span>
                </label>
                <Input unstyled
                  value={(form.price_text as string) || ''}
                  onChange={(v) => update('price_text', v)}
                  placeholder="Price text"
                  className="rounded border border-slate-200 px-3 py-2 flex-1"
                />
              </div>
            </div>
            <label htmlFor="evt-family-friendly" className="flex items-center gap-2">
              <Checkbox
                id="evt-family-friendly"
                checked={!!form.is_family_friendly}
                onChange={(e) => update('is_family_friendly', e.target.checked)}
              />
              <span className="text-sm">Family friendly</span>
            </label>
            <div>
              <label htmlFor="evt-external-url" className="block text-sm text-slate-600 mb-1">External URL</label>
              <Input unstyled
                id="evt-external-url"
                value={(form.external_url as string) || ''}
                onChange={(v) => update('external_url', v)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              />
            </div>
            <div>
              <label htmlFor="evt-source" className="block text-sm text-slate-600 mb-1">Source</label>
              <select
                id="evt-source"
                value={(form.source_id as string) || ''}
                onChange={(e) => update('source_id', e.target.value || null)}
                className="w-full rounded border border-slate-200 px-3 py-2"
              >
                <option value="">None</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.source_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </Card>

        <Card padding="lg">
          <h3 className="font-semibold mb-3 text-amber-800">Admin Only</h3>
          <div>
            <label htmlFor="evt-internal-notes" className="block text-sm text-slate-600 mb-1">Internal Notes</label>
            <textarea
              id="evt-internal-notes"
              value={(form.internal_notes as string) || ''}
              onChange={(e) => update('internal_notes', e.target.value)}
              rows={4}
              className="w-full rounded border border-slate-200 px-3 py-2"
            />
          </div>
        </Card>

        {!isNew && (
          <>
            <Card padding="lg" className="lg:col-span-2">
              <h3 className="font-semibold mb-3">Public preview</h3>
              <div className="p-4 border border-slate-200 rounded-lg bg-slate-50">
                <div className="font-medium text-[#0b2b43]">{(form.title as string) || 'Untitled'}</div>
                {form.description ? <p className="text-sm text-slate-600 mt-1">{form.description as string}</p> : null}
                {form.venue_name ? <p className="text-xs text-slate-500 mt-1">{form.venue_name as string}</p> : null}
                {form.start_datetime ? <p className="text-sm mt-1">{new Date(form.start_datetime as string).toLocaleString()}</p> : null}
                {form.is_free ? <span className="text-xs text-green-600">Free</span> : form.price_text ? <span className="text-sm">{form.price_text as string}</span> : null}
                {form.is_family_friendly ? <span className="text-xs text-slate-500 ml-2">Family-friendly</span> : null}
              </div>
            </Card>
            <Card padding="lg" className="lg:col-span-2">
              <InternalThreadPanel
                targetType="live_event"
                targetId={id}
                title="Internal discussion"
              />
            </Card>
            <Card padding="lg" className="lg:col-span-2">
              <h3 className="font-semibold mb-3">Audit log</h3>
              <div className="space-y-1 text-sm max-h-48 overflow-y-auto">
                {auditEntries.length === 0 && <p className="text-slate-500">No audit entries yet.</p>}
                {auditEntries.map((entry, i) => (
                  <div key={i} className="flex flex-wrap gap-2 py-1 border-b border-slate-100 last:border-0">
                    <span className="font-medium">{String(entry.action_type)}</span>
                    {entry.previous_status && entry.new_status && <span className="text-slate-500">{entry.previous_status} → {entry.new_status}</span>}
                    <span className="text-slate-400 text-xs">{entry.created_at ? new Date(entry.created_at).toLocaleString() : ''}</span>
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
