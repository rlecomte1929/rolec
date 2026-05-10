import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card, Button, Alert } from '../../components/antigravity';
import { suppliersAPI } from '../../api/client';
import { ROUTE_DEFS } from '../../navigation/routes';

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

export const AdminSupplierNew: React.FC = () => {
  const navigate = useNavigate();
  const [categories, setCategories] = useState<string[]>(SERVICE_CATEGORIES as unknown as string[]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: '',
    legal_name: '',
    status: 'active' as 'active' | 'inactive' | 'draft',
    description: '',
    website: '',
    contact_email: '',
    contact_phone: '',
    languages_supported: '',
    verified: false,
    capabilities: [] as Array<{
      service_category: string;
      coverage_scope_type: string;
      country_code: string;
      city_name: string;
      specialization_tags: string;
      min_budget: string;
      max_budget: string;
      family_support: boolean;
      corporate_clients: boolean;
      remote_support: boolean;
      notes: string;
    }>,
    scoring: { average_rating: '', review_count: '0', response_sla_hours: '', preferred_partner: false, premium_partner: false },
  });

  useEffect(() => {
    suppliersAPI.getCategories().then((r) => r.categories && setCategories(r.categories)).catch(() => {});
  }, []);

  const updateForm = useCallback((patch: Record<string, unknown>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  }, []);

  const addCapability = useCallback(() => {
    setForm((prev) => ({
      ...prev,
      capabilities: [
        ...prev.capabilities,
        {
          service_category: 'movers',
          coverage_scope_type: 'country',
          country_code: '',
          city_name: '',
          specialization_tags: '',
          min_budget: '',
          max_budget: '',
          family_support: false,
          corporate_clients: false,
          remote_support: false,
          notes: '',
        },
      ],
    }));
  }, []);

  const updateCapability = useCallback((idx: number, patch: Record<string, unknown>) => {
    setForm((prev) => {
      const next = [...prev.capabilities];
      next[idx] = { ...next[idx], ...patch };
      return { ...prev, capabilities: next };
    });
  }, []);

  const removeCapability = useCallback((idx: number) => {
    setForm((prev) => ({
      ...prev,
      capabilities: prev.capabilities.filter((_, i) => i !== idx),
    }));
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      if (!form.name.trim()) {
        setError('Name is required');
        return;
      }
      setLoading(true);
      try {
        const payload: Record<string, unknown> = {
          name: form.name.trim(),
          legal_name: form.legal_name.trim() || undefined,
          status: form.status,
          description: form.description.trim() || undefined,
          website: form.website.trim() || undefined,
          contact_email: form.contact_email.trim() || undefined,
          contact_phone: form.contact_phone.trim() || undefined,
          languages_supported: form.languages_supported
            ? form.languages_supported.split(/[,\s]+/).filter(Boolean)
            : [],
          verified: form.verified,
          capabilities: form.capabilities.map((c) => ({
            service_category: c.service_category,
            coverage_scope_type: c.coverage_scope_type,
            country_code: c.country_code.trim().toUpperCase().slice(0, 2) || undefined,
            city_name: c.city_name.trim() || undefined,
            specialization_tags: c.specialization_tags ? c.specialization_tags.split(/[,\s]+/).filter(Boolean) : [],
            min_budget: c.min_budget ? parseFloat(c.min_budget) : undefined,
            max_budget: c.max_budget ? parseFloat(c.max_budget) : undefined,
            family_support: c.family_support,
            corporate_clients: c.corporate_clients,
            remote_support: c.remote_support,
            notes: c.notes.trim() || undefined,
          })),
          scoring: {
            average_rating: form.scoring.average_rating ? parseFloat(form.scoring.average_rating) : undefined,
            review_count: parseInt(form.scoring.review_count, 10) || 0,
            response_sla_hours: form.scoring.response_sla_hours ? parseInt(form.scoring.response_sla_hours, 10) : undefined,
            preferred_partner: form.scoring.preferred_partner,
            premium_partner: form.scoring.premium_partner,
          },
        };
        const created = await suppliersAPI.create(payload);
        navigate(ROUTE_DEFS.adminSuppliersDetail.path.replace(':id', created.id));
      } catch (err: unknown) {
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : (err as Error)?.message;
        setError(String(msg || 'Failed to create supplier'));
      } finally {
        setLoading(false);
      }
    },
    [form, navigate]
  );

  return (
    <AdminLayout title="New Supplier" subtitle="Add a supplier to the registry">
      <Card padding="lg">
        {error && (
          <Alert variant="error" className="mb-4">
            {error}
          </Alert>
        )}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => updateForm({ name: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                placeholder="Supplier display name"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Legal name</label>
              <input
                type="text"
                value={form.legal_name}
                onChange={(e) => updateForm({ legal_name: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Status</label>
              <select
                value={form.status}
                onChange={(e) => updateForm({ status: e.target.value as 'active' | 'inactive' | 'draft' })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="draft">Draft</option>
              </select>
            </div>
            <div className="flex items-end gap-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.verified}
                  onChange={(e) => updateForm({ verified: e.target.checked })}
                />
                <span className="text-sm text-[#374151]">Verified</span>
              </label>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-[#374151] mb-1">Description</label>
              <textarea
                value={form.description}
                onChange={(e) => updateForm({ description: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                rows={2}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Website</label>
              <input
                type="url"
                value={form.website}
                onChange={(e) => updateForm({ website: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Contact email</label>
              <input
                type="email"
                value={form.contact_email}
                onChange={(e) => updateForm({ contact_email: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Contact phone</label>
              <input
                type="text"
                value={form.contact_phone}
                onChange={(e) => updateForm({ contact_phone: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Languages (comma-separated)</label>
              <input
                type="text"
                value={form.languages_supported}
                onChange={(e) => updateForm({ languages_supported: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                placeholder="en, no, de"
              />
            </div>
          </div>

          <div className="border-t border-[#e5e7eb] pt-4">
            <h3 className="text-base font-medium text-[#0b2b43] mb-2">Scoring / Verification</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm text-[#6b7280] mb-1">Rating</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="5"
                  value={form.scoring.average_rating}
                  onChange={(e) => updateForm({ scoring: { ...form.scoring, average_rating: e.target.value } })}
                  className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                  placeholder="4.0"
                />
              </div>
              <div>
                <label className="block text-sm text-[#6b7280] mb-1">Review count</label>
                <input
                  type="number"
                  min="0"
                  value={form.scoring.review_count}
                  onChange={(e) => updateForm({ scoring: { ...form.scoring, review_count: e.target.value } })}
                  className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-[#6b7280] mb-1">SLA (hours)</label>
                <input
                  type="number"
                  min="0"
                  value={form.scoring.response_sla_hours}
                  onChange={(e) => updateForm({ scoring: { ...form.scoring, response_sla_hours: e.target.value } })}
                  className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-end gap-4">
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.scoring.preferred_partner}
                    onChange={(e) => updateForm({ scoring: { ...form.scoring, preferred_partner: e.target.checked } })}
                  />
                  <span className="text-sm">Preferred</span>
                </label>
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.scoring.premium_partner}
                    onChange={(e) => updateForm({ scoring: { ...form.scoring, premium_partner: e.target.checked } })}
                  />
                  <span className="text-sm">Premium</span>
                </label>
              </div>
            </div>
          </div>

          <div className="border-t border-[#e5e7eb] pt-4">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-base font-medium text-[#0b2b43]">Service Capabilities</h3>
              <Button type="button" variant="outline" size="sm" onClick={addCapability}>
                + Add capability
              </Button>
            </div>
            {form.capabilities.length === 0 ? (
              <p className="text-sm text-[#6b7280]">No capabilities yet. Add at least one for the supplier to appear in recommendations.</p>
            ) : (
              <div className="space-y-4">
                {form.capabilities.map((cap, idx) => (
                  <div key={idx} className="border border-[#e5e7eb] rounded-lg p-4 bg-[#f9fafb]">
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-sm font-medium text-[#374151]">Capability {idx + 1}</span>
                      <Button type="button" variant="outline" size="sm" onClick={() => removeCapability(idx)}>
                        Remove
                      </Button>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                      <div>
                        <label className="block text-xs text-[#6b7280] mb-0.5">Service</label>
                        <select
                          value={cap.service_category}
                          onChange={(e) => updateCapability(idx, { service_category: e.target.value })}
                          className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                        >
                          {categories.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-[#6b7280] mb-0.5">Coverage</label>
                        <select
                          value={cap.coverage_scope_type}
                          onChange={(e) => updateCapability(idx, { coverage_scope_type: e.target.value })}
                          className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                        >
                          {COVERAGE_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t}
                            </option>
                          ))}
                        </select>
                      </div>
                      {cap.coverage_scope_type !== 'global' && (
                        <div>
                          <label className="block text-xs text-[#6b7280] mb-0.5">Country (2-letter)</label>
                          <input
                            type="text"
                            value={cap.country_code}
                            onChange={(e) => updateCapability(idx, { country_code: e.target.value.toUpperCase().slice(0, 2) })}
                            className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                            placeholder="NO"
                          />
                        </div>
                      )}
                      {cap.coverage_scope_type === 'city' && (
                        <div>
                          <label className="block text-xs text-[#6b7280] mb-0.5">City</label>
                          <input
                            type="text"
                            value={cap.city_name}
                            onChange={(e) => updateCapability(idx, { city_name: e.target.value })}
                            className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                            placeholder="Oslo"
                          />
                        </div>
                      )}
                      <div>
                        <label className="block text-xs text-[#6b7280] mb-0.5">Min budget</label>
                        <input
                          type="number"
                          value={cap.min_budget}
                          onChange={(e) => updateCapability(idx, { min_budget: e.target.value })}
                          className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-[#6b7280] mb-0.5">Max budget</label>
                        <input
                          type="number"
                          value={cap.max_budget}
                          onChange={(e) => updateCapability(idx, { max_budget: e.target.value })}
                          className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-xs text-[#6b7280] mb-0.5">Tags (comma-separated)</label>
                        <input
                          type="text"
                          value={cap.specialization_tags}
                          onChange={(e) => updateCapability(idx, { specialization_tags: e.target.value })}
                          className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                          placeholder="international, premium"
                        />
                      </div>
                    </div>
                    <div className="flex gap-4 mt-2">
                      <label className="flex items-center gap-1 cursor-pointer text-sm">
                        <input
                          type="checkbox"
                          checked={cap.family_support}
                          onChange={(e) => updateCapability(idx, { family_support: e.target.checked })}
                        />
                        Family
                      </label>
                      <label className="flex items-center gap-1 cursor-pointer text-sm">
                        <input
                          type="checkbox"
                          checked={cap.corporate_clients}
                          onChange={(e) => updateCapability(idx, { corporate_clients: e.target.checked })}
                        />
                        Corporate
                      </label>
                      <label className="flex items-center gap-1 cursor-pointer text-sm">
                        <input
                          type="checkbox"
                          checked={cap.remote_support}
                          onChange={(e) => updateCapability(idx, { remote_support: e.target.checked })}
                        />
                        Remote
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-3 pt-4">
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating...' : 'Create supplier'}
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate(ROUTE_DEFS.adminSuppliers.path)}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </AdminLayout>
  );
};
