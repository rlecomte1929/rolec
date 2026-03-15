import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card, Button, Alert } from '../../components/antigravity';
import { suppliersAPI } from '../../api/client';
import { ROUTE_DEFS } from '../../navigation/routes';

type Capability = {
  id: string;
  service_category: string;
  coverage_scope_type: string;
  country_code?: string;
  city_name?: string;
  specialization_tags: string[];
  min_budget?: number;
  max_budget?: number;
  family_support: boolean;
  corporate_clients: boolean;
  remote_support: boolean;
  notes?: string;
};

type Scoring = {
  average_rating?: number;
  review_count: number;
  response_sla_hours?: number;
  preferred_partner: boolean;
  premium_partner: boolean;
  admin_score?: number | null;
  manual_priority?: number | null;
  last_verified_at?: string;
};

type SupplierDetail = {
  id: string;
  name: string;
  legal_name?: string;
  status: string;
  description?: string;
  website?: string;
  contact_email?: string;
  contact_phone?: string;
  languages_supported: string[];
  verified: boolean;
  vendor_id?: string;
  created_at?: string;
  updated_at?: string;
  capabilities?: Capability[];
  scoring?: Scoring | null;
};

const SERVICE_CATEGORIES = [
  'living_areas',
  'schools',
  'movers',
  'banks',
  'insurance',
  'electricity',
  'childcare',
  'medical',
  'telecom',
  'storage',
  'transport',
] as const;

const COVERAGE_TYPES = ['global', 'country', 'city'] as const;

function CoverageSummary({ capabilities }: { capabilities: Capability[] }) {
  const hasGlobal = capabilities.some((c) => c.coverage_scope_type === 'global');
  const countries = [...new Set(capabilities.filter((c) => c.country_code).map((c) => c.country_code))].sort();
  const cityCaps = capabilities.filter((c) => c.coverage_scope_type === 'city' && c.city_name && c.country_code);

  return (
    <div className="space-y-4">
      <div>
        <dt className="text-[#6b7280] text-sm mb-1">Countries covered</dt>
        <dd className="text-sm text-[#0b2b43]">
          {hasGlobal ? 'Global (all countries)' : countries.length ? countries.join(', ') : '—'}
        </dd>
      </div>
      {cityCaps.length > 0 && (
        <div>
          <dt className="text-[#6b7280] text-sm mb-1">City-specific coverage</dt>
          <dd className="text-sm text-[#0b2b43]">
            {cityCaps.map((c) => `${c.city_name} (${c.country_code})`).join('; ')}
          </dd>
        </div>
      )}
    </div>
  );
}

export const AdminSupplierDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [supplier, setSupplier] = useState<SupplierDetail | null>(null);
  const [categories, setCategories] = useState<string[]>(SERVICE_CATEGORIES as unknown as string[]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<SupplierDetail>>({});
  const [addingCapability, setAddingCapability] = useState(false);
  const [newCap, setNewCap] = useState({
    service_category: 'movers',
    coverage_scope_type: 'country' as string,
    country_code: '',
    city_name: '',
    specialization_tags: [] as string[],
    min_budget: undefined as number | undefined,
    max_budget: undefined as number | undefined,
    family_support: false,
    corporate_clients: false,
    remote_support: false,
    notes: '',
  });

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const s = await suppliersAPI.get(id);
      setSupplier(s);
      setEditForm({});
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to load supplier'));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
    suppliersAPI.getCategories().then((r) => r.categories && setCategories(r.categories)).catch(() => {});
  }, [load]);

  const updateField = useCallback((field: keyof SupplierDetail, value: unknown) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  }, []);

  const saveSupplier = useCallback(async () => {
    if (!id || Object.keys(editForm).length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {};
      if (editForm.name !== undefined) payload.name = editForm.name;
      if (editForm.legal_name !== undefined) payload.legal_name = editForm.legal_name;
      if (editForm.status !== undefined) payload.status = editForm.status;
      if (editForm.description !== undefined) payload.description = editForm.description;
      if (editForm.website !== undefined) payload.website = editForm.website;
      if (editForm.contact_email !== undefined) payload.contact_email = editForm.contact_email;
      if (editForm.contact_phone !== undefined) payload.contact_phone = editForm.contact_phone;
      if (editForm.languages_supported !== undefined) payload.languages_supported = editForm.languages_supported;
      if (editForm.verified !== undefined) payload.verified = editForm.verified;
      const updated = await suppliersAPI.update(id, payload);
      setSupplier(updated);
      setEditForm({});
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to update'));
    } finally {
      setSaving(false);
    }
  }, [id, editForm]);

  const setStatus = useCallback(
    async (status: 'active' | 'inactive' | 'draft') => {
      if (!id) return;
      setSaving(true);
      setError(null);
      try {
        const updated = await suppliersAPI.setStatus(id, status);
        setSupplier(updated);
        setEditForm((prev) => ({ ...prev, status }));
      } catch (err: unknown) {
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : (err as Error)?.message;
        setError(String(msg || 'Failed to update status'));
      } finally {
        setSaving(false);
      }
    },
    [id]
  );

  const addCapability = useCallback(async () => {
    if (!id) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        service_category: newCap.service_category,
        coverage_scope_type: newCap.coverage_scope_type,
        country_code: newCap.country_code?.trim().toUpperCase().slice(0, 2) || undefined,
        city_name: newCap.city_name?.trim() || undefined,
        specialization_tags: newCap.specialization_tags,
        min_budget: newCap.min_budget,
        max_budget: newCap.max_budget,
        family_support: newCap.family_support,
        corporate_clients: newCap.corporate_clients,
        remote_support: newCap.remote_support,
        notes: newCap.notes?.trim() || undefined,
      };
      const updated = await suppliersAPI.addCapability(id, payload);
      setSupplier(updated);
      setAddingCapability(false);
      setNewCap({
        service_category: 'movers',
        coverage_scope_type: 'country',
        country_code: '',
        city_name: '',
        specialization_tags: [],
        min_budget: undefined,
        max_budget: undefined,
        family_support: false,
        corporate_clients: false,
        remote_support: false,
        notes: '',
      });
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to add capability'));
    } finally {
      setSaving(false);
    }
  }, [id, newCap]);

  const removeCapability = useCallback(
    async (capId: string) => {
      if (!id || !confirm('Remove this capability?')) return;
      setSaving(true);
      setError(null);
      try {
        const updated = await suppliersAPI.removeCapability(id, capId);
        setSupplier(updated);
      } catch (err: unknown) {
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : (err as Error)?.message;
        setError(String(msg || 'Failed to remove capability'));
      } finally {
        setSaving(false);
      }
    },
    [id]
  );

  const saveScoring = useCallback(
    async (payload: Record<string, unknown>) => {
      if (!id) return;
      setSaving(true);
      setError(null);
      try {
        const updated = await suppliersAPI.updateScoring(id, payload);
        setSupplier(updated);
      } catch (err: unknown) {
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : (err as Error)?.message;
        setError(String(msg || 'Failed to update scoring'));
      } finally {
        setSaving(false);
      }
    },
    [id]
  );

  if (!id) return null;

  if (loading && !supplier) {
    return (
      <AdminLayout title="Supplier" subtitle="Loading...">
        <Card padding="lg">Loading...</Card>
      </AdminLayout>
    );
  }

  if (error && !supplier) {
    return (
      <AdminLayout title="Supplier" subtitle="Error">
        <Card padding="lg">
          <Alert variant="error">{error}</Alert>
          <Button className="mt-4" onClick={() => navigate(ROUTE_DEFS.adminSuppliers.path)}>
            Back to list
          </Button>
        </Card>
      </AdminLayout>
    );
  }

  if (!supplier) return null;

  const display = { ...supplier, ...editForm };
  const hasEdits = Object.keys(editForm).length > 0;

  return (
    <AdminLayout title={display.name} subtitle={display.legal_name || display.status}>
      <div className="space-y-6">
        {error && (
          <Alert variant="error">
            {error}
            <Button variant="outline" size="sm" className="ml-2" onClick={() => setError(null)}>
              Dismiss
            </Button>
          </Alert>
        )}

        {supplier.capabilities && supplier.capabilities.length > 0 && (
          <Card padding="lg">
            <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Coverage</h2>
            <CoverageSummary capabilities={supplier.capabilities} />
          </Card>
        )}

        <Card padding="lg">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Contact & notes</h2>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-[#6b7280]">Website</dt>
              <dd>
                {display.website ? (
                  <a
                    href={display.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#0b2b43] underline"
                  >
                    {display.website}
                  </a>
                ) : (
                  <span className="text-[#9ca3af]">—</span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-[#6b7280]">Email</dt>
              <dd>{display.contact_email || <span className="text-[#9ca3af]">—</span>}</dd>
            </div>
            <div>
              <dt className="text-[#6b7280]">Phone</dt>
              <dd>{display.contact_phone || <span className="text-[#9ca3af]">—</span>}</dd>
            </div>
          </dl>
          {display.description && (
            <div className="mt-4 pt-4 border-t border-[#e5e7eb]">
              <dt className="text-[#6b7280] text-sm mb-1">Notes</dt>
              <dd className="text-sm text-[#4b5563]">{display.description}</dd>
            </div>
          )}
        </Card>

        <Card padding="lg">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-lg font-semibold text-[#0b2b43]">Edit details</h2>
            <Button variant="outline" size="sm" onClick={() => navigate(ROUTE_DEFS.adminSuppliers.path)}>
              ← Back to list
            </Button>
          </div>

          <div className="flex flex-wrap gap-2 mb-4">
            <span className="text-sm font-medium text-[#6b7280]">Status:</span>
            <div className="flex gap-1">
              {(['active', 'inactive', 'draft'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatus(s)}
                  disabled={saving || display.status === s}
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    display.status === s ? 'bg-[#0b2b43] text-white' : 'bg-[#f1f5f9] text-[#4b5563] hover:bg-[#e2e8f0]'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-[#6b7280]">Name</dt>
              <dd>
                <input
                  type="text"
                  value={display.name}
                  onChange={(e) => updateField('name', e.target.value)}
                  className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                />
              </dd>
            </div>
            <div>
              <dt className="text-[#6b7280]">Legal name</dt>
              <dd>
                <input
                  type="text"
                  value={display.legal_name || ''}
                  onChange={(e) => updateField('legal_name', e.target.value)}
                  className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                />
              </dd>
            </div>
            <div>
              <dt className="text-[#6b7280]">Verified</dt>
              <dd>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={display.verified}
                    onChange={(e) => updateField('verified', e.target.checked)}
                  />
                  <span>Verified partner</span>
                </label>
              </dd>
            </div>
            <div>
              <dt className="text-[#6b7280]">Website</dt>
              <dd>
                <input
                  type="url"
                  value={display.website || ''}
                  onChange={(e) => updateField('website', e.target.value)}
                  className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                />
              </dd>
            </div>
            <div>
              <dt className="text-[#6b7280]">Email</dt>
              <dd>
                <input
                  type="email"
                  value={display.contact_email || ''}
                  onChange={(e) => updateField('contact_email', e.target.value)}
                  className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                />
              </dd>
            </div>
            <div>
              <dt className="text-[#6b7280]">Phone</dt>
              <dd>
                <input
                  type="text"
                  value={display.contact_phone || ''}
                  onChange={(e) => updateField('contact_phone', e.target.value)}
                  className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                />
              </dd>
            </div>
            <div>
              <dt className="text-[#6b7280]">Languages (comma-separated)</dt>
              <dd>
                <input
                  type="text"
                  value={(display.languages_supported || []).join(', ')}
                  onChange={(e) => updateField('languages_supported', e.target.value.split(/[,\s]+/).filter(Boolean))}
                  className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                />
              </dd>
            </div>
          </dl>
          {display.description != null && (
            <div className="mt-4 pt-4 border-t border-[#e5e7eb]">
              <dt className="text-[#6b7280] text-sm mb-1">Description</dt>
              <dd>
                <textarea
                  value={display.description || ''}
                  onChange={(e) => updateField('description', e.target.value)}
                  className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                  rows={2}
                />
              </dd>
            </div>
          )}
          <div className="mt-6 pt-4 border-t border-[#e5e7eb] flex items-center justify-between">
            <span className="text-sm text-[#6b7280]">
              {hasEdits && !saving && 'You have unsaved changes'}
              {saving && 'Saving…'}
              {!hasEdits && !saving && 'All changes saved'}
            </span>
            <Button onClick={saveSupplier} disabled={saving || !hasEdits}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </Card>

        <Card padding="lg">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Scoring / Verification</h2>
          {supplier.scoring ? (
            <ScoringEditor
              scoring={supplier.scoring}
              onSave={saveScoring}
              saving={saving}
            />
          ) : (
            <p className="text-sm text-[#6b7280]">No scoring data. Add via API or seed.</p>
          )}
        </Card>

        {id && (
          <RankingDebugCard supplierId={id} supplierName={supplier.name} capabilities={supplier.capabilities || []} />
        )}

        <Card padding="lg">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-[#0b2b43]">Service Capabilities</h2>
            {!addingCapability ? (
              <Button variant="outline" size="sm" onClick={() => setAddingCapability(true)}>
                + Add capability
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setAddingCapability(false)}>
                Cancel
              </Button>
            )}
          </div>

          {addingCapability && (
            <div className="border border-[#e5e7eb] rounded-lg p-4 mb-4 bg-[#f9fafb]">
              <h3 className="text-sm font-medium text-[#374151] mb-2">New capability</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs text-[#6b7280] mb-0.5">Service</label>
                  <select
                    value={newCap.service_category}
                    onChange={(e) => setNewCap((c) => ({ ...c, service_category: e.target.value }))}
                    className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                  >
                    {categories.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-[#6b7280] mb-0.5">Coverage</label>
                  <select
                    value={newCap.coverage_scope_type}
                    onChange={(e) => setNewCap((c) => ({ ...c, coverage_scope_type: e.target.value }))}
                    className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                  >
                    {COVERAGE_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                {newCap.coverage_scope_type !== 'global' && (
                  <div>
                    <label className="block text-xs text-[#6b7280] mb-0.5">Country</label>
                    <input
                      type="text"
                      value={newCap.country_code}
                      onChange={(e) => setNewCap((c) => ({ ...c, country_code: e.target.value.toUpperCase().slice(0, 2) }))}
                      className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                      placeholder="NO"
                    />
                  </div>
                )}
                {newCap.coverage_scope_type === 'city' && (
                  <div>
                    <label className="block text-xs text-[#6b7280] mb-0.5">City</label>
                    <input
                      type="text"
                      value={newCap.city_name}
                      onChange={(e) => setNewCap((c) => ({ ...c, city_name: e.target.value }))}
                      className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                      placeholder="Oslo"
                    />
                  </div>
                )}
                <div>
                  <label className="block text-xs text-[#6b7280] mb-0.5">Min budget</label>
                  <input
                    type="number"
                    value={newCap.min_budget ?? ''}
                    onChange={(e) => setNewCap((c) => ({ ...c, min_budget: e.target.value ? parseFloat(e.target.value) : undefined }))}
                    className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#6b7280] mb-0.5">Max budget</label>
                  <input
                    type="number"
                    value={newCap.max_budget ?? ''}
                    onChange={(e) => setNewCap((c) => ({ ...c, max_budget: e.target.value ? parseFloat(e.target.value) : undefined }))}
                    className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                  />
                </div>
              </div>
              <div className="flex gap-4 mt-2">
                <label className="flex items-center gap-1 cursor-pointer text-sm">
                  <input
                    type="checkbox"
                    checked={newCap.family_support}
                    onChange={(e) => setNewCap((c) => ({ ...c, family_support: e.target.checked }))}
                  />
                  Family
                </label>
                <label className="flex items-center gap-1 cursor-pointer text-sm">
                  <input
                    type="checkbox"
                    checked={newCap.corporate_clients}
                    onChange={(e) => setNewCap((c) => ({ ...c, corporate_clients: e.target.checked }))}
                  />
                  Corporate
                </label>
                <label className="flex items-center gap-1 cursor-pointer text-sm">
                  <input
                    type="checkbox"
                    checked={newCap.remote_support}
                    onChange={(e) => setNewCap((c) => ({ ...c, remote_support: e.target.checked }))}
                  />
                  Remote
                </label>
              </div>
              <Button className="mt-3" size="sm" onClick={addCapability} disabled={saving}>
                {saving ? 'Adding...' : 'Add'}
              </Button>
            </div>
          )}

          {supplier.capabilities && supplier.capabilities.length > 0 ? (
            <div className="space-y-4">
              {supplier.capabilities.map((c) => (
                <div key={c.id} className="border border-[#e5e7eb] rounded-lg p-4 flex justify-between items-start">
                  <div>
                    <div className="font-medium text-[#0b2b43]">{c.service_category}</div>
                    <div className="text-sm text-[#6b7280] mt-1">
                      {c.coverage_scope_type}
                      {c.country_code && ` • ${c.country_code}`}
                      {c.city_name && ` • ${c.city_name}`}
                    </div>
                    {c.specialization_tags?.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {c.specialization_tags.map((t) => (
                          <span key={t} className="px-2 py-0.5 bg-[#e5e7eb] rounded text-xs">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                    {(c.family_support || c.corporate_clients || c.remote_support) && (
                      <div className="mt-2 text-xs">
                        {c.family_support && 'Family '}
                        {c.corporate_clients && 'Corporate '}
                        {c.remote_support && 'Remote'}
                      </div>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => removeCapability(c.id)}
                    disabled={saving}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            !addingCapability && (
              <p className="text-sm text-[#6b7280]">No capabilities. Add one for the supplier to appear in recommendations.</p>
            )
          )}
        </Card>
      </div>
    </AdminLayout>
  );
};

function ScoringEditor({
  scoring,
  onSave,
  saving,
}: {
  scoring: Scoring;
  onSave: (p: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const [local, setLocal] = useState({
    average_rating: scoring.average_rating ?? '',
    review_count: String(scoring.review_count ?? 0),
    response_sla_hours: scoring.response_sla_hours ?? '',
    preferred_partner: scoring.preferred_partner,
    premium_partner: scoring.premium_partner,
    admin_score: scoring.admin_score != null ? String(scoring.admin_score) : '',
    manual_priority: scoring.manual_priority != null ? String(scoring.manual_priority) : '',
  });

  useEffect(() => {
    setLocal({
      average_rating: scoring.average_rating ?? '',
      review_count: String(scoring.review_count ?? 0),
      response_sla_hours: scoring.response_sla_hours ?? '',
      preferred_partner: scoring.preferred_partner,
      premium_partner: scoring.premium_partner,
      admin_score: scoring.admin_score != null ? String(scoring.admin_score) : '',
      manual_priority: scoring.manual_priority != null ? String(scoring.manual_priority) : '',
    });
  }, [scoring]);

  const handleSave = () => {
    onSave({
      average_rating: local.average_rating ? parseFloat(String(local.average_rating)) : undefined,
      review_count: parseInt(String(local.review_count), 10) || 0,
      response_sla_hours: local.response_sla_hours ? parseInt(String(local.response_sla_hours), 10) : undefined,
      preferred_partner: local.preferred_partner,
      premium_partner: local.premium_partner,
      admin_score: local.admin_score ? parseFloat(String(local.admin_score)) : undefined,
      manual_priority: local.manual_priority ? parseInt(String(local.manual_priority), 10) : undefined,
    });
  };

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <dt className="text-[#6b7280]">Rating</dt>
          <dd>
            <input
              type="number"
              step="0.1"
              min="0"
              max="5"
              value={local.average_rating}
              onChange={(e) => setLocal((l) => ({ ...l, average_rating: e.target.value }))}
              className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
            />
          </dd>
        </div>
        <div>
          <dt className="text-[#6b7280]">Reviews</dt>
          <dd>
            <input
              type="number"
              min="0"
              value={local.review_count}
              onChange={(e) => setLocal((l) => ({ ...l, review_count: e.target.value }))}
              className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
            />
          </dd>
        </div>
        <div>
          <dt className="text-[#6b7280]">SLA (h)</dt>
          <dd>
            <input
              type="number"
              min="0"
              value={local.response_sla_hours}
              onChange={(e) => setLocal((l) => ({ ...l, response_sla_hours: e.target.value }))}
              className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
            />
          </dd>
        </div>
        <div>
          <dt className="text-[#6b7280]">Admin score (0–100)</dt>
          <dd>
            <input
              type="number"
              step="1"
              min="0"
              max="100"
              value={local.admin_score}
              onChange={(e) => setLocal((l) => ({ ...l, admin_score: e.target.value }))}
              className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
              placeholder="Optional boost"
            />
          </dd>
        </div>
        <div>
          <dt className="text-[#6b7280]">Manual priority</dt>
          <dd>
            <input
              type="number"
              value={local.manual_priority}
              onChange={(e) => setLocal((l) => ({ ...l, manual_priority: e.target.value }))}
              className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
              placeholder="Higher = rank higher"
            />
          </dd>
        </div>
        <div>
          <dt className="text-[#6b7280]">Flags</dt>
          <dd className="flex gap-4">
            <label className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={local.preferred_partner}
                onChange={(e) => setLocal((l) => ({ ...l, preferred_partner: e.target.checked }))}
              />
              <span>Preferred</span>
            </label>
            <label className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={local.premium_partner}
                onChange={(e) => setLocal((l) => ({ ...l, premium_partner: e.target.checked }))}
              />
              <span>Premium</span>
            </label>
          </dd>
        </div>
      </dl>
      <Button size="sm" onClick={handleSave} disabled={saving}>
        {saving ? 'Saving...' : 'Save scoring'}
      </Button>
    </div>
  );
}

function RankingDebugCard({
  supplierId,
}: {
  supplierId: string;
  supplierName: string;
  capabilities: Capability[];
}) {
  const [serviceCategory, setServiceCategory] = useState('movers');
  const [destinationCountry, setDestinationCountry] = useState('GB');
  const [destinationCity, setDestinationCity] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    would_match_search: boolean;
    match_reason: string;
    status?: string;
    coverage_summary?: string;
    scoring?: Record<string, unknown>;
  } | null>(null);

  const runCheck = async () => {
    setLoading(true);
    setResult(null);
    try {
      const data = await suppliersAPI.getRankingDebug(supplierId, {
        service_category: serviceCategory || undefined,
        destination_country: destinationCountry || undefined,
        destination_city: destinationCity || undefined,
      });
      setResult({
        would_match_search: data.would_match_search,
        match_reason: data.match_reason,
        status: data.status,
        coverage_summary: data.coverage_summary,
        scoring: data.scoring,
      });
    } catch {
      setResult({ would_match_search: false, match_reason: 'Request failed.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card padding="lg">
      <h2 className="text-lg font-semibold text-[#0b2b43] mb-2">Why this ranks</h2>
      <p className="text-sm text-[#6b7280] mb-4">
        Check whether this supplier would appear in recommendations for a given service and destination.
      </p>
      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <label className="block text-xs text-[#6b7280] mb-0.5">Service category</label>
          <select
            value={serviceCategory}
            onChange={(e) => setServiceCategory(e.target.value)}
            className="border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
          >
            <option value="movers">movers</option>
            <option value="living_areas">living_areas</option>
            <option value="schools">schools</option>
            <option value="banks">banks</option>
            <option value="insurance">insurance</option>
            <option value="electricity">electricity</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-[#6b7280] mb-0.5">Destination country</label>
          <input
            type="text"
            value={destinationCountry}
            onChange={(e) => setDestinationCountry(e.target.value.toUpperCase().slice(0, 2))}
            className="w-20 border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
            placeholder="GB"
          />
        </div>
        <div>
          <label className="block text-xs text-[#6b7280] mb-0.5">Destination city (optional)</label>
          <input
            type="text"
            value={destinationCity}
            onChange={(e) => setDestinationCity(e.target.value)}
            className="w-32 border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
            placeholder="London"
          />
        </div>
        <Button size="sm" onClick={runCheck} disabled={loading}>
          {loading ? 'Checking…' : 'Check'}
        </Button>
      </div>
      {result && (
        <div
          className={`text-sm p-3 rounded-lg ${
            result.would_match_search ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-amber-50 text-amber-800 border border-amber-200'
          }`}
        >
          <p className="font-medium">{result.would_match_search ? 'Included' : 'Excluded'}</p>
          <p className="mt-1">{result.match_reason}</p>
          {result.status && <p className="mt-1 text-xs">Status: {result.status}</p>}
          {result.coverage_summary && <p className="text-xs mt-1">Coverage: {result.coverage_summary}</p>}
        </div>
      )}
    </Card>
  );
}
