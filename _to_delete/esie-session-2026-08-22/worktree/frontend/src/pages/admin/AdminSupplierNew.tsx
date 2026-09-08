import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Input } from '../../components/antigravity/Input';
import { Checkbox } from '../../components/antigravity/Checkbox';
import { Card, Button, Alert } from '../../components/antigravity';
import { suppliersAPI } from '../../api/client';
import { ROUTE_DEFS } from '../../navigation/routes';
import { AdminLayout } from './AdminLayout';

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
  const [categories, setCategories] = useState<string[]>([...SERVICE_CATEGORIES]);
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
    suppliersAPI.getCategories().then((r) => r.categories && setCategories(r.categories as string[])).catch(() => {});
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
      const current = next[idx];
      if (!current) return prev;
      next[idx] = { ...current, ...patch };
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
        navigate(ROUTE_DEFS.adminSuppliersDetail.path.replace(':id', (created as { id: string }).id));
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
              <label htmlFor="sup-name" className="block text-sm font-medium text-[#374151] mb-1">Name *</label>
              <Input id="sup-name" unstyled
                type="text"
                value={form.name}
                onChange={(v) => updateForm({ name: v })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                placeholder="Supplier display name"
                required
              />
            </div>
            <div>
              <label htmlFor="sup-legal-name" className="block text-sm font-medium text-[#374151] mb-1">Legal name</label>
              <Input id="sup-legal-name" unstyled
                type="text"
                value={form.legal_name}
                onChange={(v) => updateForm({ legal_name: v })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="sup-status" className="block text-sm font-medium text-[#374151] mb-1">Status</label>
              <select id="sup-status"
                value={form.status}
                onChange={(e) => updateForm({ status: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="draft">Draft</option>
              </select>
            </div>
            <div className="flex items-end gap-2">
              <label htmlFor="sup-updateform-verified" className="flex items-center gap-2 cursor-pointer">
                <Checkbox id="sup-updateform-verified"
                  checked={form.verified}
                  onChange={(e) => updateForm({ verified: e.target.checked })}
                />
                <span className="text-sm text-[#374151]">Verified</span>
              </label>
            </div>
            <div className="md:col-span-2">
              <label htmlFor="sup-description" className="block text-sm font-medium text-[#374151] mb-1">Description</label>
              <textarea id="sup-description"
                value={form.description}
                onChange={(e) => updateForm({ description: e.target.value })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                rows={2}
              />
            </div>
            <div>
              <label htmlFor="sup-website" className="block text-sm font-medium text-[#374151] mb-1">Website</label>
              <Input id="sup-website" unstyled
                type="url"
                value={form.website}
                onChange={(v) => updateForm({ website: v })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="sup-contact-email" className="block text-sm font-medium text-[#374151] mb-1">Contact email</label>
              <Input id="sup-contact-email" unstyled
                type="email"
                value={form.contact_email}
                onChange={(v) => updateForm({ contact_email: v })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="sup-contact-phone" className="block text-sm font-medium text-[#374151] mb-1">Contact phone</label>
              <Input id="sup-contact-phone" unstyled
                type="text"
                value={form.contact_phone}
                onChange={(v) => updateForm({ contact_phone: v })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="sup-languages-commaseparated" className="block text-sm font-medium text-[#374151] mb-1">Languages (comma-separated)</label>
              <Input id="sup-languages-commaseparated" unstyled
                type="text"
                value={form.languages_supported}
                onChange={(v) => updateForm({ languages_supported: v })}
                className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                placeholder="en, no, de"
              />
            </div>
          </div>

          <div className="border-t border-[#e5e7eb] pt-4">
            <h3 className="text-base font-medium text-[#0b2b43] mb-2">Scoring / Verification</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label htmlFor="sup-rating" className="block text-sm text-[#6b7280] mb-1">Rating</label>
                <Input id="sup-rating" unstyled
                  type="number"
                  step="0.1"
                  min="0"
                  max="5"
                  value={form.scoring.average_rating}
                  onChange={(v) => updateForm({ scoring: { ...form.scoring, average_rating: v } })}
                  className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                  placeholder="4.0"
                />
              </div>
              <div>
                <label htmlFor="sup-review-count" className="block text-sm text-[#6b7280] mb-1">Review count</label>
                <Input id="sup-review-count" unstyled
                  type="number"
                  min="0"
                  value={form.scoring.review_count}
                  onChange={(v) => updateForm({ scoring: { ...form.scoring, review_count: v } })}
                  className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="sup-sla-hours" className="block text-sm text-[#6b7280] mb-1">SLA (hours)</label>
                <Input id="sup-sla-hours" unstyled
                  type="number"
                  min="0"
                  value={form.scoring.response_sla_hours}
                  onChange={(v) => updateForm({ scoring: { ...form.scoring, response_sla_hours: v } })}
                  className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-end gap-4">
                <label htmlFor="sup-updateform-scoring-preferred" className="flex items-center gap-1 cursor-pointer">
                  <Checkbox id="sup-updateform-scoring-preferred"
                    checked={form.scoring.preferred_partner}
                    onChange={(e) => updateForm({ scoring: { ...form.scoring, preferred_partner: e.target.checked } })}
                  />
                  <span className="text-sm">Preferred</span>
                </label>
                <label htmlFor="sup-updateform-scoring-premium" className="flex items-center gap-1 cursor-pointer">
                  <Checkbox id="sup-updateform-scoring-premium"
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
                        <label htmlFor="sup-service" className="block text-xs text-[#6b7280] mb-0.5">Service</label>
                        <select id="sup-service"
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
                        <label htmlFor="sup-coverage" className="block text-xs text-[#6b7280] mb-0.5">Coverage</label>
                        <select id="sup-coverage"
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
                          <label htmlFor="sup-country-2letter" className="block text-xs text-[#6b7280] mb-0.5">Country (2-letter)</label>
                          <Input id="sup-country-2letter" unstyled
                            type="text"
                            value={cap.country_code}
                            onChange={(v) => updateCapability(idx, { country_code: v.toUpperCase().slice(0, 2) })}
                            className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                            placeholder="NO"
                          />
                        </div>
                      )}
                      {cap.coverage_scope_type === 'city' && (
                        <div>
                          <label htmlFor="sup-city" className="block text-xs text-[#6b7280] mb-0.5">City</label>
                          <Input id="sup-city" unstyled
                            type="text"
                            value={cap.city_name}
                            onChange={(v) => updateCapability(idx, { city_name: v })}
                            className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                            placeholder="Oslo"
                          />
                        </div>
                      )}
                      <div>
                        <label htmlFor="sup-min-budget" className="block text-xs text-[#6b7280] mb-0.5">Min budget</label>
                        <Input id="sup-min-budget" unstyled
                          type="number"
                          value={cap.min_budget}
                          onChange={(v) => updateCapability(idx, { min_budget: v })}
                          className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                        />
                      </div>
                      <div>
                        <label htmlFor="sup-max-budget" className="block text-xs text-[#6b7280] mb-0.5">Max budget</label>
                        <Input id="sup-max-budget" unstyled
                          type="number"
                          value={cap.max_budget}
                          onChange={(v) => updateCapability(idx, { max_budget: v })}
                          className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label htmlFor="sup-tags-commaseparated" className="block text-xs text-[#6b7280] mb-0.5">Tags (comma-separated)</label>
                        <Input id="sup-tags-commaseparated" unstyled
                          type="text"
                          value={cap.specialization_tags}
                          onChange={(v) => updateCapability(idx, { specialization_tags: v })}
                          className="w-full border border-[#d1d5db] rounded px-2 py-1.5 text-sm"
                          placeholder="international, premium"
                        />
                      </div>
                    </div>
                    <div className="flex gap-4 mt-2">
                      <label htmlFor="sup-updatecapabilityidx-family" className="flex items-center gap-1 cursor-pointer text-sm">
                        <Checkbox id="sup-updatecapabilityidx-family"
                          checked={cap.family_support}
                          onChange={(e) => updateCapability(idx, { family_support: e.target.checked })}
                        />
                        Family
                      </label>
                      <label htmlFor="sup-updatecapabilityidx-corporat" className="flex items-center gap-1 cursor-pointer text-sm">
                        <Checkbox id="sup-updatecapabilityidx-corporat"
                          checked={cap.corporate_clients}
                          onChange={(e) => updateCapability(idx, { corporate_clients: e.target.checked })}
                        />
                        Corporate
                      </label>
                      <label htmlFor="sup-updatecapabilityidx-remote" className="flex items-center gap-1 cursor-pointer text-sm">
                        <Checkbox id="sup-updatecapabilityidx-remote"
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
