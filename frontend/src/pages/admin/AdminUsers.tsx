import React, { useEffect, useState } from 'react';
import { Card, Button, Badge } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { adminAPI } from '../../api/client';
import type { AdminProfile, AdminCompany } from '../../types';

const ROLE_OPTIONS = [
  { value: '', label: 'All roles' },
  { value: 'admin', label: 'Admin' },
  { value: 'hr', label: 'HR' },
  { value: 'employee', label: 'Employee' },
];

export const AdminUsers: React.FC = () => {
  const [query, setQuery] = useState('');
  const [companyId, setCompanyId] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [people, setPeople] = useState<AdminProfile[]>([]);
  const [companies, setCompanies] = useState<AdminCompany[]>([]);
  const [loading, setLoading] = useState(false);
  const [editOpen, setEditOpen] = useState<AdminProfile | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [deleteFeedback, setDeleteFeedback] = useState<'idle' | 'deleting' | 'done' | 'error'>('idle');

  const loadPeople = async () => {
    setLoading(true);
    try {
      const res = await adminAPI.listPeople({
        q: query || undefined,
        company_id: companyId || undefined,
        role: roleFilter || undefined,
      });
      setPeople(res.people ?? []);
      return res.people ?? [];
    } finally {
      setLoading(false);
    }
  };

  const loadCompanies = async () => {
    const res = await adminAPI.listCompanies();
    setCompanies(res.companies ?? []);
  };

  useEffect(() => {
    loadCompanies().catch(() => undefined);
  }, []);

  useEffect(() => {
    loadPeople().catch(() => undefined);
  }, [companyId, roleFilter]);

  return (
    <AdminLayout title="People" subtitle="HR and employee accounts — filter by company and role, edit and assign">
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <label className="block text-xs font-medium text-[#6b7280] mb-0.5">Company</label>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              className="rounded-lg border border-[#d1d5db] px-3 py-2 text-sm min-w-[180px]"
            >
              <option value="">All companies</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-[#6b7280] mb-0.5">Role</label>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
            >
              {ROLE_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-[#6b7280] mb-0.5">Search</label>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name or email"
              className="rounded-lg border border-[#d1d5db] px-3 py-2 text-sm w-48"
            />
          </div>
          <div className="self-end">
            <Button onClick={() => loadPeople()} disabled={loading}>
              {loading ? 'Loading…' : 'Apply'}
            </Button>
          </div>
          <div className="self-end ml-auto flex items-center gap-2 flex-wrap">
            {!selectionMode ? (
              <>
                <Button variant="outline" onClick={() => setSelectionMode(true)}>
                  Edit
                </Button>
                <Button variant="primary" onClick={() => setAddOpen(true)}>
                  Add person
                </Button>
              </>
            ) : (
              <>
                {deleteFeedback === 'done' && (
                  <span className="text-sm text-green-600">Deleted. List updated.</span>
                )}
                {deleteFeedback === 'error' && (
                  <span className="text-sm text-red-600">Delete failed or list could not refresh.</span>
                )}
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectionMode(false);
                    setSelectedIds(new Set());
                    setDeleteFeedback('idle');
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="outline"
                  disabled={selectedIds.size === 0 || deleteFeedback === 'deleting'}
                  onClick={async () => {
                    if (selectedIds.size === 0) return;
                    if (!window.confirm(`Delete ${selectedIds.size} selected people?`)) return;
                    if (!window.confirm('Are you sure? This action cannot be undone.')) return;
                    const ids = Array.from(selectedIds);
                    setDeleteFeedback('deleting');
                    setSelectedIds(new Set());
                    try {
                      const results = await Promise.allSettled(
                        ids.map((id) => adminAPI.deactivatePerson(id)),
                      );
                      const failed = results.filter((r) => r.status === 'rejected').length;
                      const nextPeople = await loadPeople();
                      setDeleteFeedback(failed > 0 ? 'error' : 'done');
                      if (failed === 0 && nextPeople) {
                        setSelectionMode(false);
                        setTimeout(() => setDeleteFeedback('idle'), 3000);
                      } else if (failed > 0) {
                        setTimeout(() => setDeleteFeedback('idle'), 5000);
                      }
                    } catch (e) {
                      console.error(e);
                      await loadPeople();
                      setDeleteFeedback('error');
                      setTimeout(() => setDeleteFeedback('idle'), 5000);
                    }
                  }}
                >
                  {deleteFeedback === 'deleting' ? 'Deleting…' : 'Delete selected'}
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>
      <Card padding="lg">
        {(() => {
          const total = people.length;
          const hrCount = people.filter((p) => p.role === 'HR' || ((p as { hr_link_count?: number }).hr_link_count ?? 0) > 0).length;
          const employeeCount = people.filter((p) => ['EMPLOYEE', 'EMPLOYEE_USER'].includes(p.role || '') || ((p as { employee_link_count?: number }).employee_link_count ?? 0) > 0).length;
          return (
            <div className="text-sm text-[#6b7280] mb-3 flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="font-medium text-[#0b2b43]">People ({total})</span>
              <span>HR: {hrCount}</span>
              <span>Employees: {employeeCount}</span>
            </div>
          );
        })()}
        <div className="space-y-3">
          {people.map((p) => {
            const checked = selectedIds.has(p.id);
            return (
            <div key={p.id} className="flex flex-wrap items-center justify-between border-b border-[#e2e8f0] py-3 gap-3">
              <div className="flex items-start gap-3">
                {selectionMode && (
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-[#cbd5e1]"
                    checked={checked}
                    onChange={(e) => {
                      setSelectedIds((prev) => {
                        const next = new Set(prev);
                        if (e.target.checked) next.add(p.id);
                        else next.delete(p.id);
                        return next;
                      });
                    }}
                  />
                )}
              <div>
                <div className="font-medium text-[#0b2b43]">{p.name || p.full_name || p.email || p.id}</div>
                <div className="text-xs text-[#6b7280]">{p.email || '—'} · {p.id}</div>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="neutral" size="sm">{(p.role || '').toUpperCase()}</Badge>
                  {p.company_name ? (
                    <span className="text-xs px-2 py-0.5 rounded bg-[#f1f5f9] text-[#475569]">{p.company_name}</span>
                  ) : p.company_id ? (
                    <span className="text-xs text-amber-600">Company {p.company_id}</span>
                  ) : (
                    <span className="text-xs text-[#94a3b8]">Unassigned</span>
                  )}
                  {(p.status || 'active').toLowerCase() === 'inactive' && (
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">Inactive</span>
                  )}
                </div>
              </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Button size="sm" variant="outline" onClick={() => setEditOpen(p)}>
                  Edit
                </Button>
              </div>
            </div>
          )})}
          {people.length === 0 && !loading && (
            <div className="py-12 text-center text-[#6b7280] border border-dashed border-[#e5e7eb] rounded-lg bg-[#f9fafb]">
              <div className="text-sm font-medium">No people found</div>
              <div className="text-xs mt-1">
                {companyId || roleFilter || query ? 'Try changing filters or search.' : 'Profiles appear when users register or are provisioned. Use Add person above to provision.'}
              </div>
            </div>
          )}
        </div>
      </Card>

      {editOpen && (
        <EditPersonModal
          person={editOpen}
          companies={companies}
          onClose={() => setEditOpen(null)}
          onSaved={() => {
            setEditOpen(null);
            loadPeople();
          }}
        />
      )}
      {addOpen && (
        <AddPersonModal
          companies={companies}
          onClose={() => setAddOpen(false)}
          onCreated={() => {
            setAddOpen(false);
            loadPeople();
          }}
        />
      )}
    </AdminLayout>
  );
};

interface EditPersonModalProps {
  person: AdminProfile;
  companies: AdminCompany[];
  onClose: () => void;
  onSaved: () => void;
}

const EditPersonModal: React.FC<EditPersonModalProps> = ({ person, companies, onClose, onSaved }) => {
  const [full_name, setFullName] = useState(person.full_name ?? '');
  const [role, setRole] = useState(person.role ?? 'EMPLOYEE');
  const [company_id, setCompanyId] = useState(person.company_id ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await adminAPI.updatePerson(person.id, {
        full_name: full_name.trim() || undefined,
        role: role.toUpperCase(),
        company_id: company_id || undefined,
      });
      onSaved();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Edit person</h2>
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Email</label>
            <input value={person.email ?? ''} readOnly className="w-full rounded-lg border border-[#e5e7eb] bg-[#f9fafb] px-3 py-2 text-sm text-[#6b7280]" />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Name</label>
            <input
              value={full_name}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm"
              placeholder="Full name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm">
              <option value="ADMIN">Admin</option>
              <option value="HR">HR</option>
              <option value="EMPLOYEE">Employee</option>
              <option value="EMPLOYEE_USER">Employee (user)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Company</label>
            <select value={company_id} onChange={(e) => setCompanyId(e.target.value)} className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm">
              <option value="">Unassigned</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          {error && <div className="text-sm text-red-600">{error}</div>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface AddPersonModalProps {
  companies: AdminCompany[];
  onClose: () => void;
  onCreated: () => void;
}

const AddPersonModal: React.FC<AddPersonModalProps> = ({ companies, onClose, onCreated }) => {
  const [email, setEmail] = useState('');
  const [full_name, setFullName] = useState('');
  const [role, setRole] = useState('EMPLOYEE');
  const [company_id, setCompanyId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) {
      setError('Email is required');
      return;
    }
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      await adminAPI.createPerson({
        email: trimmed,
        full_name: full_name.trim() || undefined,
        role,
        company_id: company_id || undefined,
      });
      setSuccess('Person created.');
      onCreated();
    } catch (err: any) {
      const detail = err?.response?.data;
      let message = err?.message || 'Failed to create person';
      if (typeof detail === 'string') {
        message = detail;
      } else if (detail?.message) {
        message = detail.message;
      }
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Add person</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Email *</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm" placeholder="email@example.com" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Name</label>
            <input value={full_name} onChange={(e) => setFullName(e.target.value)} className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm" placeholder="Full name" />
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm">
              <option value="ADMIN">Admin</option>
              <option value="HR">HR</option>
              <option value="EMPLOYEE">Employee</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Company</label>
            <select value={company_id} onChange={(e) => setCompanyId(e.target.value)} className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm">
              <option value="">Unassigned</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          {error && <div className="text-sm text-red-600">{error}</div>}
          {success && <div className="text-sm text-green-600">{success}</div>}
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={submitting}>{submitting ? 'Creating…' : 'Create'}</Button>
          </div>
        </form>
      </div>
    </div>
  );
};
