import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminResourcesAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';

type Tag = { id: string; key: string; label: string; tag_group?: string };

const TAG_GROUPS = ['age_group', 'budget', 'family_type', 'free_paid', 'indoor_outdoor', 'interest', 'weekday_weekend'];

export const AdminTags: React.FC = () => {
  const [items, setItems] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [newKey, setNewKey] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newGroup, setNewGroup] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [filterGroup, setFilterGroup] = useState('');
  const [search, setSearch] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminResourcesAPI.listTags(filterGroup || undefined);
      setItems(res.tags || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [filterGroup]);

  const update = async (id: string, payload: { key?: string; label?: string; tag_group?: string }) => {
    try {
      await adminResourcesAPI.updateTag(id, payload);
      setEditing(null);
      load();
    } catch (e) {
      alert((e as Error).message || 'Update failed');
    }
  };

  const filteredItems = search.trim()
    ? items.filter((t) => (t.label?.toLowerCase().includes(search.toLowerCase())) || (t.key?.toLowerCase().includes(search.toLowerCase())))
    : items;

  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Tags" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  const create = async () => {
    if (!newKey.trim() || !newLabel.trim()) return;
    try {
      await adminResourcesAPI.createTag({
        key: newKey.trim().toLowerCase().replace(/\s+/g, '_'),
        label: newLabel.trim(),
        tag_group: newGroup || undefined,
      });
      setNewKey('');
      setNewLabel('');
      setNewGroup('');
      load();
    } catch (e) {
      alert((e as Error).message || 'Create failed');
    }
  };

  return (
    <AdminLayout title="Tags" subtitle="Manage resource tags">
      <Link to={buildRoute('adminResources')} className="inline-block mb-4">
        <Button variant="secondary">← Back to Resources CMS</Button>
      </Link>

      <Card padding="lg" className="mb-4">
        <h3 className="font-semibold mb-3">New Tag</h3>
        <div className="flex gap-2 flex-wrap items-center">
          <input
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="Key (e.g. family_friendly)"
            className="rounded border border-slate-200 px-3 py-2 w-40"
          />
          <input
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            placeholder="Label (e.g. Family Friendly)"
            className="rounded border border-slate-200 px-3 py-2 w-40"
          />
          <select
            value={newGroup}
            onChange={(e) => setNewGroup(e.target.value)}
            className="rounded border border-slate-200 px-3 py-2"
          >
            <option value="">— group —</option>
            {TAG_GROUPS.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
          <Button onClick={create} variant="primary">
            Create
          </Button>
        </div>
      </Card>

      <Card padding="lg">
        <div className="flex gap-4 mb-3 flex-wrap">
          <select
            value={filterGroup}
            onChange={(e) => setFilterGroup(e.target.value)}
            className="rounded border border-slate-200 px-2 py-1 text-sm"
          >
            <option value="">All groups</option>
            {TAG_GROUPS.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by label/key"
            className="rounded border border-slate-200 px-2 py-1 text-sm w-48"
          />
          <span className="text-sm text-slate-500 self-center">{filteredItems.length} tags</span>
        </div>
        <div className="space-y-2">
          {filteredItems.map((t) => (
            <div key={t.id} className="flex items-center justify-between border-b border-slate-100 py-2">
              <div>
                <span className="font-medium">{t.label}</span>
                <span className="text-slate-500 ml-2">({t.key})</span>
                {t.tag_group && <span className="text-slate-400 ml-2">[{t.tag_group}]</span>}
              </div>
              {editing === t.id ? (
                <div className="flex gap-2 flex-wrap">
                  <input
                    className="rounded border border-slate-200 px-2 py-1 text-sm w-28"
                    defaultValue={t.label}
                    id={`edit-label-${t.id}`}
                    placeholder="Label"
                  />
                  <input
                    className="rounded border border-slate-200 px-2 py-1 text-sm w-28"
                    defaultValue={t.key}
                    id={`edit-key-${t.id}`}
                    placeholder="Key"
                  />
                  <select
                    defaultValue={t.tag_group || ''}
                    id={`edit-group-${t.id}`}
                    className="rounded border border-slate-200 px-2 py-1 text-sm"
                  >
                    <option value="">—</option>
                    {TAG_GROUPS.map((g) => (
                      <option key={g} value={g}>{g}</option>
                    ))}
                  </select>
                  <Button size="sm" onClick={() => {
                    const labelInp = document.getElementById(`edit-label-${t.id}`) as HTMLInputElement;
                    const keyInp = document.getElementById(`edit-key-${t.id}`) as HTMLInputElement;
                    const groupInp = document.getElementById(`edit-group-${t.id}`) as HTMLSelectElement;
                    if (labelInp?.value) update(t.id, { label: labelInp.value, key: keyInp?.value || t.key, tag_group: groupInp?.value || undefined });
                  }}>Save</Button>
                  <Button size="sm" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
                </div>
              ) : (
                <Button size="sm" variant="secondary" onClick={() => setEditing(t.id)}>Edit</Button>
              )}
            </div>
          ))}
        </div>
        {filteredItems.length === 0 && !loading && (
          <div className="py-6 text-center text-slate-500">No tags yet.</div>
        )}
      </Card>
    </AdminLayout>
  );
};
