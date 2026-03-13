import React, { useState, useEffect } from 'react';
import { Container } from '../components/antigravity';
import { hrPreferredSuppliersAPI } from '../api/client';
import { suppliersAPI } from '../api/client';

const SERVICE_CATEGORIES = [
  { value: '', label: 'All categories' },
  { value: 'movers', label: 'Movers' },
  { value: 'housing', label: 'Housing' },
  { value: 'schools', label: 'Schools' },
  { value: 'banks', label: 'Banks' },
  { value: 'insurances', label: 'Insurances' },
  { value: 'electricity', label: 'Electricity' },
];

export const HrPreferredSuppliers: React.FC = () => {
  const [preferred, setPreferred] = useState<
    Array<{
      id: string;
      company_id: string;
      supplier_id: string;
      service_category: string | null;
      priority_rank: number;
      status: string;
      notes: string | null;
      created_at: string;
      supplier_name?: string;
    }>
  >([]);
  const [filterCategory, setFilterCategory] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addSupplierId, setAddSupplierId] = useState('');
  const [addServiceCategory, setAddServiceCategory] = useState('');
  const [addPriorityRank, setAddPriorityRank] = useState(0);
  const [addNotes, setAddNotes] = useState('');
  const [addSaving, setAddSaving] = useState(false);
  const [candidateSuppliers, setCandidateSuppliers] = useState<
    Array<{ id: string; name: string; status: string }>
  >([]);
  const [removeConfirm, setRemoveConfirm] = useState<{ supplier_id: string; service_category: string | null } | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await hrPreferredSuppliersAPI.list(
        filterCategory || undefined
      );
      const list = (res.preferred ?? []) as typeof preferred;
      const supplierIds = [...new Set(list.map((p) => p.supplier_id))];
      const nameMap: Record<string, string> = {};
      for (const sid of supplierIds) {
        try {
          const s = await suppliersAPI.get(sid);
          nameMap[sid] = (s as { name?: string }).name ?? sid;
        } catch {
          nameMap[sid] = sid;
        }
      }
      setPreferred(
        list.map((p) => ({
          ...p,
          supplier_name: nameMap[p.supplier_id] ?? p.supplier_id,
        }))
      );
    } catch (e) {
      setError(String((e as Error).message ?? 'Failed to load'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [filterCategory]);

  const openAddModal = async () => {
    setAddModalOpen(true);
    setAddSupplierId('');
    setAddServiceCategory('');
    setAddPriorityRank(0);
    setAddNotes('');
    try {
      const res = await suppliersAPI.list({ status: 'active', limit: 200 });
      const items = (res as { suppliers?: Array<{ id: string; name: string; status: string }> }).suppliers ?? [];
      setCandidateSuppliers(items);
    } catch {
      setCandidateSuppliers([]);
    }
  };

  const handleAdd = async () => {
    if (!addSupplierId.trim()) return;
    setAddSaving(true);
    setError(null);
    try {
      await hrPreferredSuppliersAPI.add({
        supplier_id: addSupplierId.trim(),
        service_category: addServiceCategory.trim() || undefined,
        priority_rank: addPriorityRank,
        notes: addNotes.trim() || undefined,
      });
      setAddModalOpen(false);
      load();
    } catch (e) {
      setError(String((e as Error).message ?? 'Failed to add'));
    } finally {
      setAddSaving(false);
    }
  };

  const handleRemove = async (supplier_id: string, service_category: string | null) => {
    try {
      await hrPreferredSuppliersAPI.remove(supplier_id, service_category ?? undefined);
      setRemoveConfirm(null);
      load();
    } catch (e) {
      setError(String((e as Error).message ?? 'Failed to remove'));
    }
  };

  return (
    <Container maxWidth="xl" className="py-8">
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-[#0b2b43]">Preferred Suppliers</h1>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="px-3 py-2 border border-[#e2e8f0] rounded-lg text-sm"
            >
              {SERVICE_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={openAddModal}
              className="px-4 py-2 rounded-lg bg-[#0b2b43] text-white font-medium hover:bg-[#1e3a5f]"
            >
              Add preferred supplier
            </button>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-800 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-[#6b7280]">Loading…</p>
        ) : preferred.length === 0 ? (
          <div className="p-8 rounded-xl border border-[#e2e8f0] bg-white text-center text-[#6b7280]">
            No preferred suppliers yet. Add suppliers from the registry to surface them prominently to employees.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0]">
                  <th className="text-left py-3 px-4 font-semibold text-[#0b2b43]">Supplier</th>
                  <th className="text-left py-3 px-4 font-semibold text-[#0b2b43]">Service</th>
                  <th className="text-left py-3 px-4 font-semibold text-[#0b2b43]">Priority</th>
                  <th className="text-left py-3 px-4 font-semibold text-[#0b2b43]">Notes</th>
                  <th className="text-right py-3 px-4 font-semibold text-[#0b2b43]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {preferred.map((p) => (
                  <tr key={`${p.supplier_id}-${p.service_category ?? ''}`} className="border-b border-[#e2e8f0] hover:bg-[#f8fafc]">
                    <td className="py-3 px-4 font-medium">{p.supplier_name ?? p.supplier_id}</td>
                    <td className="py-3 px-4 text-sm">{p.service_category ?? 'All'}</td>
                    <td className="py-3 px-4 text-sm">{p.priority_rank}</td>
                    <td className="py-3 px-4 text-sm text-[#6b7280] max-w-xs truncate">
                      {p.notes ?? '—'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {removeConfirm?.supplier_id === p.supplier_id &&
                      removeConfirm?.service_category === (p.service_category ?? null) ? (
                        <span className="flex items-center justify-end gap-2">
                          <span className="text-sm text-[#6b7280]">Remove?</span>
                          <button
                            type="button"
                            onClick={() => handleRemove(p.supplier_id, p.service_category)}
                            className="text-sm text-red-600 hover:underline"
                          >
                            Yes
                          </button>
                          <button
                            type="button"
                            onClick={() => setRemoveConfirm(null)}
                            className="text-sm text-[#6b7280] hover:underline"
                          >
                            No
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() =>
                            setRemoveConfirm({
                              supplier_id: p.supplier_id,
                              service_category: p.service_category ?? null,
                            })
                          }
                          className="text-sm text-red-600 hover:underline"
                        >
                          Remove
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {addModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Add preferred supplier</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#4b5563] mb-1">Supplier</label>
                <select
                  value={addSupplierId}
                  onChange={(e) => setAddSupplierId(e.target.value)}
                  className="w-full px-3 py-2 border border-[#e2e8f0] rounded-lg"
                >
                  <option value="">Select supplier</option>
                  {candidateSuppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#4b5563] mb-1">Service category</label>
                <select
                  value={addServiceCategory}
                  onChange={(e) => setAddServiceCategory(e.target.value)}
                  className="w-full px-3 py-2 border border-[#e2e8f0] rounded-lg"
                >
                  <option value="">All</option>
                  {SERVICE_CATEGORIES.filter((c) => c.value).map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#4b5563] mb-1">Priority (lower = higher)</label>
                <input
                  type="number"
                  value={addPriorityRank}
                  onChange={(e) => setAddPriorityRank(parseInt(e.target.value, 10) || 0)}
                  className="w-full px-3 py-2 border border-[#e2e8f0] rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#4b5563] mb-1">Notes</label>
                <textarea
                  value={addNotes}
                  onChange={(e) => setAddNotes(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 border border-[#e2e8f0] rounded-lg"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                type="button"
                onClick={() => setAddModalOpen(false)}
                className="px-4 py-2 rounded-lg border border-[#e2e8f0] text-[#4b5563] hover:bg-[#f5f7fa]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAdd}
                disabled={!addSupplierId.trim() || addSaving}
                className="px-4 py-2 rounded-lg bg-[#0b2b43] text-white font-medium hover:bg-[#1e3a5f] disabled:opacity-50"
              >
                {addSaving ? 'Adding…' : 'Add'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Container>
  );
};
