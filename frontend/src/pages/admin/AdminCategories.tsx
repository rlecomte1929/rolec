import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminResourcesAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';

type Category = { id: string; key: string; label: string; description?: string; icon_name?: string; sort_order?: number; is_active?: boolean };

export const AdminCategories: React.FC = () => {
  const [items, setItems] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [newKey, setNewKey] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newIcon, setNewIcon] = useState('');
  const [newSortOrder, setNewSortOrder] = useState(0);

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminResourcesAPI.listCategories();
      setItems(res.categories || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Categories" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  const create = async () => {
    if (!newKey.trim() || !newLabel.trim()) return;
    try {
      await adminResourcesAPI.createCategory({
        key: newKey.trim(),
        label: newLabel.trim(),
        icon_name: newIcon.trim() || undefined,
        sort_order: newSortOrder,
      });
      setNewKey('');
      setNewLabel('');
      setNewIcon('');
      setNewSortOrder(0);
      load();
    } catch (e) {
      alert((e as Error).message || 'Create failed');
    }
  };

  const update = async (id: string, payload: { key?: string; label?: string; description?: string; icon_name?: string; sort_order?: number }) => {
    try {
      await adminResourcesAPI.updateCategory(id, payload);
      setEditing(null);
      load();
    } catch (e) {
      alert((e as Error).message || 'Update failed');
    }
  };

  const deactivate = async (id: string) => {
    if (!confirm('Deactivate this category? It will no longer appear in dropdowns.')) return;
    try {
      await adminResourcesAPI.deactivateCategory(id);
      load();
    } catch (e) {
      alert((e as Error).message || 'Deactivate failed');
    }
  };

  return (
    <AdminLayout title="Categories" subtitle="Manage resource categories">
      <Link to={buildRoute('adminResources')} className="inline-block mb-4">
        <Button variant="secondary">← Back to Resources CMS</Button>
      </Link>

      <Card padding="lg" className="mb-4">
        <h3 className="font-semibold mb-3">New Category</h3>
        <div className="flex gap-2 flex-wrap items-center">
          <input
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="Key (e.g. schools)"
            className="rounded border border-slate-200 px-3 py-2 w-40"
          />
          <input
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            placeholder="Label (e.g. Schools)"
            className="rounded border border-slate-200 px-3 py-2 w-40"
          />
          <input
            value={newIcon}
            onChange={(e) => setNewIcon(e.target.value)}
            placeholder="Icon name"
            className="rounded border border-slate-200 px-3 py-2 w-32"
          />
          <input
            type="number"
            value={newSortOrder}
            onChange={(e) => setNewSortOrder(parseInt(e.target.value, 10) || 0)}
            placeholder="Sort order"
            className="rounded border border-slate-200 px-3 py-2 w-24"
          />
          <Button onClick={create} variant="primary">
            Create
          </Button>
        </div>
      </Card>

      <Card padding="lg">
        <div className="text-sm text-slate-500 mb-2">{items.length} categories</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left">
                <th className="py-2 pr-4">Label</th>
                <th className="py-2 pr-4">Key</th>
                <th className="py-2 pr-4">Icon</th>
                <th className="py-2 pr-4">Sort</th>
                <th className="py-2 pr-4">Active</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className={`border-b border-slate-100 py-2 ${c.is_active === false ? 'opacity-60' : ''}`}>
                  <td className="py-2 pr-4">
                    {editing === c.id ? (
                      <input
                        className="rounded border border-slate-200 px-2 py-1 w-32"
                        defaultValue={c.label}
                        id={`edit-label-${c.id}`}
                      />
                    ) : (
                      <span className="font-medium">{c.label}</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-slate-500">{c.key}</td>
                  <td className="py-2 pr-4">{editing === c.id ? (
                    <input
                      className="rounded border border-slate-200 px-2 py-1 w-24"
                      defaultValue={c.icon_name || ''}
                      id={`edit-icon-${c.id}`}
                    />
                  ) : (
                    c.icon_name || '-'
                  )}</td>
                  <td className="py-2 pr-4">{editing === c.id ? (
                    <input
                      type="number"
                      className="rounded border border-slate-200 px-2 py-1 w-16"
                      defaultValue={c.sort_order ?? 0}
                      id={`edit-sort-${c.id}`}
                    />
                  ) : (
                    c.sort_order ?? 0
                  )}</td>
                  <td className="py-2 pr-4">{c.is_active !== false ? 'Yes' : 'No'}</td>
                  <td className="py-2">
                    {editing === c.id ? (
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          onClick={() => {
                            const labelInp = document.getElementById(`edit-label-${c.id}`) as HTMLInputElement;
                            const iconInp = document.getElementById(`edit-icon-${c.id}`) as HTMLInputElement;
                            const sortInp = document.getElementById(`edit-sort-${c.id}`) as HTMLInputElement;
                            update(c.id, {
                              label: labelInp?.value,
                              icon_name: iconInp?.value || undefined,
                              sort_order: sortInp?.value ? parseInt(sortInp.value, 10) : undefined,
                            });
                          }}
                        >
                          Save
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
                      </div>
                    ) : (
                      <div className="flex gap-1">
                        <Button size="sm" variant="secondary" onClick={() => setEditing(c.id)}>Edit</Button>
                        {c.is_active !== false && (
                          <Button size="sm" variant="secondary" onClick={() => deactivate(c.id)}>Deactivate</Button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {items.length === 0 && !loading && (
          <div className="py-6 text-center text-slate-500">No categories yet.</div>
        )}
      </Card>
    </AdminLayout>
  );
};
