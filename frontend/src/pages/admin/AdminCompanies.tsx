import React, { useEffect, useMemo, useState } from 'react';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type { AdminCompany, CompanyPlanTier } from '../../types';
import { Link } from 'react-router-dom';

const PLAN_OPTIONS: { value: CompanyPlanTier; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'premium', label: 'Premium' },
];

type SortKey =
  | 'name'
  | 'status'
  | 'plan'
  | 'country'
  | 'size_band'
  | 'hr_users_count'
  | 'employee_count'
  | 'assignments_count'
  | 'contact'
  | null;

export const AdminCompanies: React.FC = () => {
  const [query, setQuery] = useState('');
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<AdminCompany>>({});
  const [filterNameCol, setFilterNameCol] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPlan, setFilterPlan] = useState<'' | CompanyPlanTier>('');
  const [filterCountry, setFilterCountry] = useState('');
  const [filterSizeBand, setFilterSizeBand] = useState('');
  const [filterHrMin, setFilterHrMin] = useState('');
  const [filterEmployeesMin, setFilterEmployeesMin] = useState('');
  const [filterCasesMin, setFilterCasesMin] = useState('');
  const [filterContact, setFilterContact] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const load = async () => {
    setLoading(true);
    try {
      const res = await adminAPI.listCompanies(query || undefined);
      setCompanies(res.companies ?? []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  const canEdit = (c: AdminCompany) => !c.missing_from_companies_table;
  const planTier = (c: AdminCompany) => (c.plan_tier as CompanyPlanTier) || 'low';
  const statusLabel = (c: AdminCompany) => (c.status || 'active').toLowerCase();

  const hasColumnFilters =
    filterNameCol.trim() !== '' ||
    filterStatus !== '' ||
    filterPlan !== '' ||
    filterCountry.trim() !== '' ||
    filterSizeBand.trim() !== '' ||
    filterHrMin.trim() !== '' ||
    filterEmployeesMin.trim() !== '' ||
    filterCasesMin.trim() !== '' ||
    filterContact.trim() !== '';

  const clearColumnFilters = () => {
    setFilterNameCol('');
    setFilterStatus('');
    setFilterPlan('');
    setFilterCountry('');
    setFilterSizeBand('');
    setFilterHrMin('');
    setFilterEmployeesMin('');
    setFilterCasesMin('');
    setFilterContact('');
    setSortKey(null);
    setSortDir('asc');
  };

  const toggleSort = (key: NonNullable<SortKey>) => {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir('asc');
    } else if (sortDir === 'asc') {
      setSortDir('desc');
    } else {
      setSortKey(null);
      setSortDir('asc');
    }
  };

  const sortIndicator = (key: NonNullable<SortKey>) => {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' ↑' : ' ↓';
  };

  const filteredAndSorted = useMemo(() => {
    const nameQ = filterNameCol.trim().toLowerCase();
    const countryQ = filterCountry.trim().toLowerCase();
    const sizeQ = filterSizeBand.trim().toLowerCase();
    const contactQ = filterContact.trim().toLowerCase();
    const hrMinN = filterHrMin.trim() === '' ? null : Number(filterHrMin);
    const empMinN = filterEmployeesMin.trim() === '' ? null : Number(filterEmployeesMin);
    const casesMinN = filterCasesMin.trim() === '' ? null : Number(filterCasesMin);

    let list = companies.filter((c) => {
      if (nameQ && !(c.name || '').toLowerCase().includes(nameQ)) return false;
      if (filterStatus && statusLabel(c) !== filterStatus) return false;
      if (filterPlan && planTier(c) !== filterPlan) return false;
      if (countryQ && !(c.country || '').toLowerCase().includes(countryQ)) return false;
      if (sizeQ && !(c.size_band || '').toLowerCase().includes(sizeQ)) return false;
      if (contactQ && !(c.primary_contact_name || '').toLowerCase().includes(contactQ)) return false;
      if (hrMinN !== null && Number.isFinite(hrMinN) && (c.hr_users_count ?? 0) < hrMinN) return false;
      if (empMinN !== null && Number.isFinite(empMinN) && (c.employee_count ?? 0) < empMinN) return false;
      if (casesMinN !== null && Number.isFinite(casesMinN) && (c.assignments_count ?? 0) < casesMinN) return false;
      return true;
    });

    if (sortKey) {
      const dir = sortDir === 'asc' ? 1 : -1;
      list = [...list].sort((a, b) => {
        let va: string | number = '';
        let vb: string | number = '';
        switch (sortKey) {
          case 'name':
            va = (a.name || '').toLowerCase();
            vb = (b.name || '').toLowerCase();
            break;
          case 'status':
            va = statusLabel(a);
            vb = statusLabel(b);
            break;
          case 'plan':
            va = planTier(a);
            vb = planTier(b);
            break;
          case 'country':
            va = (a.country || '').toLowerCase();
            vb = (b.country || '').toLowerCase();
            break;
          case 'size_band':
            va = (a.size_band || '').toLowerCase();
            vb = (b.size_band || '').toLowerCase();
            break;
          case 'hr_users_count':
            va = a.hr_users_count ?? 0;
            vb = b.hr_users_count ?? 0;
            break;
          case 'employee_count':
            va = a.employee_count ?? 0;
            vb = b.employee_count ?? 0;
            break;
          case 'assignments_count':
            va = a.assignments_count ?? 0;
            vb = b.assignments_count ?? 0;
            break;
          case 'contact':
            va = (a.primary_contact_name || '').toLowerCase();
            vb = (b.primary_contact_name || '').toLowerCase();
            break;
          default:
            return 0;
        }
        if (typeof va === 'number' && typeof vb === 'number') {
          return va === vb ? 0 : va < vb ? -dir : dir;
        }
        const sa = String(va);
        const sb = String(vb);
        return sa === sb ? 0 : sa < sb ? -dir : dir;
      });
    }
    return list;
  }, [
    companies,
    filterNameCol,
    filterStatus,
    filterPlan,
    filterCountry,
    filterSizeBand,
    filterHrMin,
    filterEmployeesMin,
    filterCasesMin,
    filterContact,
    sortKey,
    sortDir,
  ]);

  const handleSave = async (companyId: string) => {
    const draft = editDraft;
    if (!Object.keys(draft).length) {
      setEditingId(null);
      setEditDraft({});
      return;
    }
    setSavingId(companyId);
    try {
      const payload: Parameters<typeof adminAPI.updateCompany>[1] = {};
      if (draft.name !== undefined) payload.name = draft.name;
      if (draft.country !== undefined) payload.country = draft.country;
      if (draft.size_band !== undefined) payload.size_band = draft.size_band;
      if (draft.status !== undefined) payload.status = draft.status;
      if (draft.plan_tier !== undefined) payload.plan_tier = draft.plan_tier;
      if (draft.hr_seat_limit !== undefined && draft.hr_seat_limit !== null) payload.hr_seat_limit = draft.hr_seat_limit;
      if (draft.employee_seat_limit !== undefined && draft.employee_seat_limit !== null) payload.employee_seat_limit = draft.employee_seat_limit;
      if (draft.address !== undefined) payload.address = draft.address;
      if (draft.phone !== undefined) payload.phone = draft.phone;
      if (draft.hr_contact !== undefined) payload.hr_contact = draft.hr_contact;
      if (draft.support_email !== undefined && draft.support_email !== null) payload.support_email = draft.support_email;
      await adminAPI.updateCompany(companyId, payload);
      setEditingId(null);
      setEditDraft({});
      await load();
    } catch (e) {
      console.error(e);
    } finally {
      setSavingId(null);
    }
  };

  const handleDeactivate = async (c: AdminCompany) => {
    if (!window.confirm(`Delete "${c.name}"? Existing assignments and policies will keep their company id, but this company will no longer be editable.`)) return;
    if (!window.confirm('Are you sure? This action cannot be undone.')) return;
    try {
      await adminAPI.deactivateCompany(c.id);
      await load();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <AdminLayout title="Companies" subtitle="Create, edit, plan tier, delete">
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by company name"
            className="w-64 rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
          />
          <Button onClick={() => load()} disabled={loading}>
            {loading ? 'Loading…' : 'Search'}
          </Button>
          <Button variant="primary" onClick={() => setAddOpen(true)}>
            Add company
          </Button>
          {hasColumnFilters && (
            <Button variant="outline" onClick={clearColumnFilters}>
              Clear table filters
            </Button>
          )}
        </div>
      </Card>
      <Card padding="lg">
        <div className="text-sm text-[#6b7280] mb-2">
          Companies (
          {hasColumnFilters ? `${filteredAndSorted.length} shown · ${companies.length} loaded` : companies.length})
        </div>
        {loading && companies.length === 0 ? (
          <div className="py-8 text-center text-[#6b7280]">Loading...</div>
        ) : companies.length === 0 ? (
          <div className="py-12 text-center text-[#6b7280] border border-dashed border-[#e5e7eb] rounded-lg bg-[#f9fafb]">
            <div className="text-sm font-medium">No companies found</div>
            <div className="text-xs mt-1">
              {query ? 'No companies match your search. Try a different query or clear search.' : 'Create a company to get started.'}
            </div>
            {!query && (
              <Button className="mt-4" variant="primary" onClick={() => setAddOpen(true)}>
                Add company
              </Button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] text-left text-[#6b7280] font-medium">
                  <th className="py-2 pr-4 align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('name')}
                      className="text-left font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      Company name{sortIndicator('name')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('status')}
                      className="text-left font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      Status{sortIndicator('status')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('plan')}
                      className="text-left font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      Plan{sortIndicator('plan')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('country')}
                      className="text-left font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      Country{sortIndicator('country')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('size_band')}
                      className="text-left font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      Size band{sortIndicator('size_band')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 text-right align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('hr_users_count')}
                      className="w-full text-right font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      HR users{sortIndicator('hr_users_count')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 text-right align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('employee_count')}
                      className="w-full text-right font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      Employees{sortIndicator('employee_count')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 text-right align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('assignments_count')}
                      className="w-full text-right font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      Cases{sortIndicator('assignments_count')}
                    </button>
                  </th>
                  <th className="py-2 pr-4 align-bottom">
                    <button
                      type="button"
                      onClick={() => toggleSort('contact')}
                      className="text-left font-medium text-[#6b7280] hover:text-[#0b2b43] cursor-pointer"
                    >
                      Contact person{sortIndicator('contact')}
                    </button>
                  </th>
                  <th className="py-2 pl-2 align-bottom text-left font-medium text-[#6b7280]">Actions</th>
                </tr>
                <tr className="border-b border-[#e2e8f0] bg-[#f8fafc] text-left">
                  <th className="py-2 pr-4 font-normal align-top">
                    <input
                      value={filterNameCol}
                      onChange={(e) => setFilterNameCol(e.target.value)}
                      placeholder="Contains…"
                      className="w-full min-w-[7rem] max-w-[11rem] rounded border border-[#d1d5db] px-2 py-1 text-xs text-[#374151]"
                      aria-label="Filter by company name"
                    />
                  </th>
                  <th className="py-2 pr-4 font-normal align-top">
                    <select
                      value={filterStatus}
                      onChange={(e) => setFilterStatus(e.target.value)}
                      className="w-full min-w-[5.5rem] max-w-[8rem] rounded border border-[#d1d5db] px-1 py-1 text-xs text-[#374151]"
                      aria-label="Filter by status"
                    >
                      <option value="">All</option>
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                      <option value="archived">Archived</option>
                    </select>
                  </th>
                  <th className="py-2 pr-4 font-normal align-top">
                    <select
                      value={filterPlan}
                      onChange={(e) => setFilterPlan((e.target.value || '') as '' | CompanyPlanTier)}
                      className="w-full min-w-[5rem] max-w-[7rem] rounded border border-[#d1d5db] px-1 py-1 text-xs text-[#374151]"
                      aria-label="Filter by plan"
                    >
                      <option value="">All</option>
                      {PLAN_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </th>
                  <th className="py-2 pr-4 font-normal align-top">
                    <input
                      value={filterCountry}
                      onChange={(e) => setFilterCountry(e.target.value)}
                      placeholder="Contains…"
                      className="w-full min-w-[4rem] max-w-[6rem] rounded border border-[#d1d5db] px-2 py-1 text-xs text-[#374151]"
                      aria-label="Filter by country"
                    />
                  </th>
                  <th className="py-2 pr-4 font-normal align-top">
                    <input
                      value={filterSizeBand}
                      onChange={(e) => setFilterSizeBand(e.target.value)}
                      placeholder="Contains…"
                      className="w-full min-w-[4rem] max-w-[6rem] rounded border border-[#d1d5db] px-2 py-1 text-xs text-[#374151]"
                      aria-label="Filter by size band"
                    />
                  </th>
                  <th className="py-2 pr-4 font-normal align-top">
                    <input
                      type="number"
                      min={0}
                      value={filterHrMin}
                      onChange={(e) => setFilterHrMin(e.target.value)}
                      placeholder="Min"
                      className="w-full min-w-[3.25rem] max-w-[4.5rem] ml-auto block rounded border border-[#d1d5db] px-1 py-1 text-xs text-[#374151] text-right tabular-nums"
                      aria-label="Minimum HR users"
                    />
                  </th>
                  <th className="py-2 pr-4 font-normal align-top">
                    <input
                      type="number"
                      min={0}
                      value={filterEmployeesMin}
                      onChange={(e) => setFilterEmployeesMin(e.target.value)}
                      placeholder="Min"
                      className="w-full min-w-[3.25rem] max-w-[4.5rem] ml-auto block rounded border border-[#d1d5db] px-1 py-1 text-xs text-[#374151] text-right tabular-nums"
                      aria-label="Minimum employees"
                    />
                  </th>
                  <th className="py-2 pr-4 font-normal align-top">
                    <input
                      type="number"
                      min={0}
                      value={filterCasesMin}
                      onChange={(e) => setFilterCasesMin(e.target.value)}
                      placeholder="Min"
                      className="w-full min-w-[3.25rem] max-w-[4.5rem] ml-auto block rounded border border-[#d1d5db] px-1 py-1 text-xs text-[#374151] text-right tabular-nums"
                      aria-label="Minimum cases"
                    />
                  </th>
                  <th className="py-2 pr-4 font-normal align-top">
                    <input
                      value={filterContact}
                      onChange={(e) => setFilterContact(e.target.value)}
                      placeholder="Contains…"
                      className="w-full min-w-[6rem] max-w-[9rem] rounded border border-[#d1d5db] px-2 py-1 text-xs text-[#374151]"
                      aria-label="Filter by contact"
                    />
                  </th>
                  <th className="py-2 pl-2 align-top" />
                </tr>
              </thead>
              <tbody>
                {filteredAndSorted.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="py-8 text-center text-[#6b7280] text-sm">
                      No companies match the table filters.{' '}
                      <button
                        type="button"
                        onClick={clearColumnFilters}
                        className="text-[#0b2b43] underline font-medium"
                      >
                        Clear filters
                      </button>
                    </td>
                  </tr>
                ) : null}
                {filteredAndSorted.map((c) => (
                  <tr key={c.id} className="border-b border-[#e2e8f0]">
                    <td className="py-3 pr-4">
                      <div className="flex items-center gap-2 flex-wrap">
                        {canEdit(c) && editingId === c.id ? (
                          <input
                            value={editDraft.name !== undefined ? editDraft.name : c.name}
                            onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))}
                            className="rounded border border-[#d1d5db] px-2 py-1 text-sm font-medium w-48"
                            placeholder="Company name"
                          />
                        ) : canEdit(c) ? (
                          <Link to={`/admin/companies/${c.id}`} className="font-medium text-[#0b2b43] hover:underline">
                            {c.name}
                          </Link>
                        ) : (
                          <span className="font-medium text-[#0b2b43]">{c.name}</span>
                        )}
                        {c.missing_from_companies_table ? (
                          <span className="text-xs text-amber-600">Not in registry</span>
                        ) : null}
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          statusLabel(c) === 'inactive' || statusLabel(c) === 'archived'
                            ? 'bg-gray-100 text-gray-700'
                            : 'bg-green-100 text-green-800'
                        }`}
                      >
                        {statusLabel(c)}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      {canEdit(c) && (
                        <select
                          value={editingId === c.id && editDraft.plan_tier !== undefined ? editDraft.plan_tier : planTier(c)}
                          onChange={(e) => {
                            if (editingId !== c.id) setEditingId(c.id);
                            setEditDraft((d) => ({ ...d, plan_tier: e.target.value as CompanyPlanTier }));
                          }}
                          className="rounded border border-[#d1d5db] px-2 py-1 text-sm"
                        >
                          {PLAN_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                      )}
                      {!canEdit(c) && <span className="text-[#374151]">{planTier(c)}</span>}
                    </td>
                    <td className="py-3 pr-4 text-[#374151]">
                      {editingId === c.id ? (
                        <input
                          value={editDraft.country !== undefined ? editDraft.country : (c.country || '')}
                          onChange={(e) => setEditDraft((d) => ({ ...d, country: e.target.value }))}
                          className="rounded border border-[#d1d5db] px-2 py-0.5 text-xs w-28"
                          placeholder="Country"
                        />
                      ) : (
                        c.country || '-'
                      )}
                    </td>
                    <td className="py-3 pr-4 text-[#374151]">{c.size_band || '-'}</td>
                    <td className="py-3 pr-4 text-right text-[#374151] tabular-nums">{c.hr_users_count ?? 0}</td>
                    <td className="py-3 pr-4 text-right text-[#374151] tabular-nums">{c.employee_count ?? 0}</td>
                    <td className="py-3 pr-4 text-right text-[#374151] tabular-nums">{c.assignments_count ?? 0}</td>
                    <td className="py-3 pr-4 text-[#374151]">{c.primary_contact_name ?? '-'}</td>
                    <td className="py-3 pl-2">
                      {canEdit(c) && (
                        <div className="flex items-center gap-1 flex-wrap">
                          {editingId === c.id ? (
                            <>
                              <Button size="sm" onClick={() => handleSave(c.id)} disabled={savingId === c.id}>
                                {savingId === c.id ? 'Saving…' : 'Save'}
                              </Button>
                              <Button size="sm" variant="outline" onClick={() => { setEditingId(null); setEditDraft({}); }}>
                                Cancel
                              </Button>
                            </>
                          ) : (
                            <Button size="sm" variant="outline" onClick={() => setEditingId(c.id)}>
                              Edit
                            </Button>
                          )}
                          {(c.status || 'active').toLowerCase() === 'active' && (
                            <Button size="sm" variant="outline" onClick={() => handleDeactivate(c)}>
                              Delete
                            </Button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {addOpen && (
        <AddCompanyModal
          onClose={() => setAddOpen(false)}
          onCreated={() => {
            setAddOpen(false);
            load();
          }}
        />
      )}
    </AdminLayout>
  );
};

interface AddCompanyModalProps {
  onClose: () => void;
  onCreated: () => void;
}

const AddCompanyModal: React.FC<AddCompanyModalProps> = ({ onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [country, setCountry] = useState('');
  const [plan_tier, setPlanTier] = useState<CompanyPlanTier>('low');
  const [status, setStatus] = useState<string>('active');
  const [hr_seat_limit, setHrSeatLimit] = useState<number | ''>('');
  const [employee_seat_limit, setEmployeeSeatLimit] = useState<number | ''>('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError('Name is required');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await adminAPI.createCompany({
        name: trimmed,
        country: country.trim() || undefined,
        plan_tier,
        status,
        hr_seat_limit: hr_seat_limit === '' ? undefined : Number(hr_seat_limit),
        employee_seat_limit: employee_seat_limit === '' ? undefined : Number(employee_seat_limit),
      });
      onCreated();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create company');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Add company</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
              placeholder="Company name"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Country</label>
            <input
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
              placeholder="e.g. Norway"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Plan tier</label>
            <select
              value={plan_tier}
              onChange={(e) => setPlanTier(e.target.value as CompanyPlanTier)}
              className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
            >
              {PLAN_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="archived">Archived</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">HR seat limit</label>
              <input
                type="number"
                min={0}
                value={hr_seat_limit}
                onChange={(e) => setHrSeatLimit(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
                placeholder="-"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Employee seat limit</label>
              <input
                type="number"
                min={0}
                value={employee_seat_limit}
                onChange={(e) => setEmployeeSeatLimit(e.target.value === '' ? '' : parseInt(e.target.value, 10))}
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
                placeholder="-"
              />
            </div>
          </div>
          {error && <div className="text-sm text-red-600">{error}</div>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create company'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
