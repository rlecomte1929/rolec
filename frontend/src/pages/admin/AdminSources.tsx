import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminResourcesAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';

type Source = { id: string; source_name: string; publisher?: string; source_type?: string; url?: string; trust_tier?: string; notes?: string; retrieved_at?: string };

const SOURCE_TYPES = ['official', 'institutional', 'commercial', 'community', 'internal_curated'];
const TRUST_TIERS = ['T0', 'T1', 'T2', 'T3'];

export const AdminSources: React.FC = () => {
  const [items, setItems] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [newPublisher, setNewPublisher] = useState('');
  const [newType, setNewType] = useState('community');
  const [newTrustTier, setNewTrustTier] = useState('T2');
  const [editing, setEditing] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminResourcesAPI.listSources();
      setItems(res.sources || []);
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
      <AdminLayout title="Sources" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  const create = async () => {
    if (!newName.trim()) return;
    try {
      await adminResourcesAPI.createSource({
        source_name: newName.trim(),
        publisher: newPublisher.trim() || undefined,
        source_type: newType,
        trust_tier: newTrustTier,
      });
      setNewName('');
      setNewPublisher('');
      load();
    } catch (e) {
      alert((e as Error).message || 'Create failed');
    }
  };

  const update = async (id: string, payload: Partial<Source>) => {
    try {
      await adminResourcesAPI.updateSource(id, payload);
      setEditing(null);
      load();
    } catch (e) {
      alert((e as Error).message || 'Update failed');
    }
  };

  return (
    <AdminLayout title="Sources" subtitle="Manage source records for provenance">
      <Link to={buildRoute('adminResources')} className="inline-block mb-4">
        <Button variant="secondary">← Back to Resources CMS</Button>
      </Link>

      <Card padding="lg" className="mb-4">
        <h3 className="font-semibold mb-3">New Source</h3>
        <div className="flex gap-2 flex-wrap items-center">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Source name"
            className="rounded border border-slate-200 px-3 py-2 w-48"
          />
          <input
            value={newPublisher}
            onChange={(e) => setNewPublisher(e.target.value)}
            placeholder="Publisher"
            className="rounded border border-slate-200 px-3 py-2 w-48"
          />
          <select value={newType} onChange={(e) => setNewType(e.target.value)} className="rounded border border-slate-200 px-3 py-2">
            {SOURCE_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select value={newTrustTier} onChange={(e) => setNewTrustTier(e.target.value)} className="rounded border border-slate-200 px-3 py-2">
            {TRUST_TIERS.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <Button onClick={create} variant="primary">
            Create
          </Button>
        </div>
      </Card>

      <Card padding="lg">
        <div className="text-sm text-slate-500 mb-2">{items.length} sources</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left">
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Publisher</th>
                <th className="py-2 pr-4">Type</th>
                <th className="py-2 pr-4">Trust</th>
                <th className="py-2 pr-4">URL</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} className="border-b border-slate-100">
                  <td className="py-2 pr-4">
                    {editing === s.id ? (
                      <input
                        className="rounded border border-slate-200 px-2 py-1 w-40"
                        defaultValue={s.source_name}
                        id={`edit-name-${s.id}`}
                      />
                    ) : (
                      <span className="font-medium">{s.source_name}</span>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    {editing === s.id ? (
                      <input
                        className="rounded border border-slate-200 px-2 py-1 w-32"
                        defaultValue={s.publisher || ''}
                        id={`edit-publisher-${s.id}`}
                      />
                    ) : (
                      s.publisher || '-'
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    {editing === s.id ? (
                      <select defaultValue={s.source_type || 'community'} id={`edit-type-${s.id}`} className="rounded border border-slate-200 px-2 py-1">
                        {SOURCE_TYPES.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    ) : (
                      s.source_type || '-'
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    {editing === s.id ? (
                      <select defaultValue={s.trust_tier || 'T2'} id={`edit-trust-${s.id}`} className="rounded border border-slate-200 px-2 py-1">
                        {TRUST_TIERS.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    ) : (
                      s.trust_tier || '-'
                    )}
                  </td>
                  <td className="py-2 pr-4 max-w-[12rem] truncate">
                    {editing === s.id ? (
                      <input
                        className="rounded border border-slate-200 px-2 py-1 w-48"
                        defaultValue={s.url || ''}
                        id={`edit-url-${s.id}`}
                        placeholder="URL"
                      />
                    ) : (
                      s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 truncate block max-w-[12rem]">{s.url}</a> : '-'
                    )}
                  </td>
                  <td className="py-2">
                    {editing === s.id ? (
                      <div className="flex gap-1">
                        <Button size="sm" onClick={() => {
                          const nameInp = document.getElementById(`edit-name-${s.id}`) as HTMLInputElement;
                          const pubInp = document.getElementById(`edit-publisher-${s.id}`) as HTMLInputElement;
                          const typeInp = document.getElementById(`edit-type-${s.id}`) as HTMLSelectElement;
                          const trustInp = document.getElementById(`edit-trust-${s.id}`) as HTMLSelectElement;
                          const urlInp = document.getElementById(`edit-url-${s.id}`) as HTMLInputElement;
                          if (nameInp?.value) update(s.id, {
                            source_name: nameInp.value,
                            publisher: pubInp?.value || undefined,
                            source_type: typeInp?.value || undefined,
                            trust_tier: trustInp?.value || undefined,
                            url: urlInp?.value || undefined,
                          });
                        }}>Save</Button>
                        <Button size="sm" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
                      </div>
                    ) : (
                      <Button size="sm" variant="secondary" onClick={() => setEditing(s.id)}>Edit</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {items.length === 0 && !loading && (
          <div className="py-6 text-center text-slate-500">No sources yet.</div>
        )}
      </Card>
    </AdminLayout>
  );
};
