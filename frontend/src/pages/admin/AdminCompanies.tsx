import React, { useEffect, useState } from 'react';
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

export const AdminCompanies: React.FC = () => {
  const [query, setQuery] = useState('');
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<AdminCompany>>({});
  const [backfillRunning, setBackfillRunning] = useState(false);
  const [backfillResult, setBackfillResult] = useState<string | null>(null);

  const runBackfill = async () => {
    if (!window.confirm('Rebuild the Test company graph? This links demo/test data to the fixed Test company without overwriting non-demo companies.')) return;
    setBackfillRunning(true);
    setBackfillResult(null);
    try {
      const res = await adminAPI.rebuildTestCompanyGraph();
      if (res.ok && res.summary) {
        const s = res.summary;
        setBackfillResult(
          `Rebuilt graph for ${s.test_company_id}: ` +
            `${s.profiles_linked} profiles, ${s.hr_users_linked} HR users, ` +
            `${s.employees_linked} employees, ${s.relocation_cases_linked} cases, ` +
            `${s.case_assignments_repaired} assignments repaired, ${s.policies_linked} policies.`
        );
        await load();
      }
    } catch (e) {
      setBackfillResult((e as Error)?.message || 'Request failed.');
    } finally {
      setBackfillRunning(false);
    }
  };

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
    if (!window.confirm(`Deactivate "${c.name}"? The company will be marked inactive. Existing references (policies, assignments) are preserved.`)) return;
    try {
      await adminAPI.deactivateCompany(c.id);
      await load();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <AdminLayout title="Companies" subtitle="Company accounts — create, edit, plan tier, and deactivate">
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
          <Button variant="outline" onClick={runBackfill} disabled={backfillRunning}>
            {backfillRunning ? 'Running…' : 'Rebuild Test company graph'}
          </Button>
          {backfillResult && (
            <span className="text-sm text-[#6b7280] self-center">{backfillResult}</span>
          )}
        </div>
      </Card>
      <Card padding="lg">
        <div className="text-sm text-[#6b7280] mb-2">Companies ({companies.length})</div>
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
                  <th className="py-2 pr-4">Company name</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Plan</th>
                  <th className="py-2 pr-4">Country</th>
                  <th className="py-2 pr-4">Size band</th>
                  <th className="py-2 pr-4 text-right">HR users</th>
                  <th className="py-2 pr-4 text-right">Employees</th>
                  <th className="py-2 pr-4 text-right">Cases</th>
                  <th className="py-2 pr-4">Contact person</th>
                  <th className="py-2 pl-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((c) => (
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
                        c.country || '—'
                      )}
                    </td>
                    <td className="py-3 pr-4 text-[#374151]">{c.size_band || '—'}</td>
                    <td className="py-3 pr-4 text-right text-[#374151] tabular-nums">{c.hr_users_count ?? 0}</td>
                    <td className="py-3 pr-4 text-right text-[#374151] tabular-nums">{c.employee_count ?? 0}</td>
                    <td className="py-3 pr-4 text-right text-[#374151] tabular-nums">{c.assignments_count ?? 0}</td>
                    <td className="py-3 pr-4 text-[#374151]">{c.primary_contact_name ?? '—'}</td>
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
                              Deactivate
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
                placeholder="—"
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
                placeholder="—"
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
