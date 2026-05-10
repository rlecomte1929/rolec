import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card, Button, Alert } from '../../components/antigravity';
import { suppliersAPI } from '../../api/client';
import { ROUTE_DEFS } from '../../navigation/routes';

/** Human-readable labels for service categories (API returns snake_case). */
const CATEGORY_LABELS: Record<string, string> = {
  movers: 'Movers',
  living_areas: 'Housing',
  schools: 'Schools',
  legal_admin: 'Immigration',
  banks: 'Banking',
  insurance: 'Insurance',
  transport: 'Transport',
  electricity: 'Electricity',
  medical: 'Medical',
  telecom: 'Telecom',
  childcare: 'Childcare',
  storage: 'Storage',
  language_integration: 'Language',
  tax_finance: 'Tax & finance',
};

function categoryLabel(value: string): string {
  return CATEGORY_LABELS[value] || value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

type Supplier = {
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
  service_categories?: string[];
  coverage_summary?: string;
};

export const AdminSuppliers: React.FC = () => {
  const navigate = useNavigate();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [countries, setCountries] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [countryFilter, setCountryFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load categories and countries on mount only: do not load suppliers yet
  useEffect(() => {
    suppliersAPI.getCategories().then((r) => r.categories && setCategories(r.categories || [])).catch(() => {});
    suppliersAPI.getCountries().then((r) => setCountries(r.countries || [])).catch(() => {});
  }, []);

  const loadSuppliers = useCallback(async () => {
    if (!selectedCategory.trim()) {
      setSuppliers([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {
        service_category: selectedCategory,
      };
      if (countryFilter) params.country_code = countryFilter;
      if (statusFilter) params.status = statusFilter;
      const res = await suppliersAPI.list(params);
      setSuppliers(res.suppliers || []);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to load suppliers'));
      setSuppliers([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, countryFilter, statusFilter]);

  // Load suppliers only when a category is selected (and when filters change)
  useEffect(() => {
    if (selectedCategory.trim()) {
      loadSuppliers();
    } else {
      setSuppliers([]);
      setError(null);
    }
  }, [selectedCategory, countryFilter, statusFilter, loadSuppliers]);

  const goToDetail = (id: string, anchor?: string) => {
    const path = ROUTE_DEFS.adminSuppliersDetail.path.replace(':id', id);
    navigate(anchor ? `${path}${anchor}` : path);
  };

  const handleSetStatus = (id: string, name: string, status: 'active' | 'inactive') => {
    if (status === 'inactive' && !window.confirm(`Deactivate ${name}? They will no longer appear in recommendations.`)) return;
    suppliersAPI.setStatus(id, status).then(loadSuppliers).catch(() => setError('Failed to update status'));
  };

  return (
    <AdminLayout title="Suppliers" subtitle="Registry by service category">
      {/* Category-first: service category selectors at the top */}
      <Card padding="lg" className="mb-4">
        <h2 className="text-sm font-medium text-[#374151] mb-3">Service category</h2>
        <p className="text-xs text-[#6b7280] mb-3">Select a category to load suppliers. No list is loaded until you choose one.</p>
        <div className="flex flex-wrap gap-2">
          {categories.map((cat) => (
            <Button
              key={cat}
              variant={selectedCategory === cat ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(cat)}
            >
              {categoryLabel(cat)}
            </Button>
          ))}
          {categories.length === 0 && (
            <span className="text-sm text-[#6b7280]">Loading categories…</span>
          )}
        </div>
      </Card>

      {/* Optional filters and Add supplier: only relevant when a category is selected */}
      {selectedCategory && (
        <Card padding="lg" className="mb-4">
          {error && (
            <Alert variant="error" className="mb-4">
              {error}
              <Button variant="outline" size="sm" className="ml-2" onClick={loadSuppliers}>
                Retry
              </Button>
            </Alert>
          )}
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <label className="block text-xs font-medium text-[#6b7280] mb-1">Country</label>
                <select
                  value={countryFilter}
                  onChange={(e) => setCountryFilter(e.target.value)}
                  className="border border-[#d1d5db] rounded px-3 py-2 text-sm min-w-[120px]"
                >
                  <option value="">All</option>
                  {countries.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-[#6b7280] mb-1">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="border border-[#d1d5db] rounded px-3 py-2 text-sm"
                >
                  <option value="">All</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="draft">Draft</option>
                </select>
              </div>
              <div className="self-end pt-6">
                <Button variant="outline" size="sm" onClick={loadSuppliers} disabled={loading}>
                  {loading ? 'Loading…' : 'Refresh'}
                </Button>
              </div>
            </div>
            <Button onClick={() => navigate(ROUTE_DEFS.adminSuppliersNew.path)}>Add supplier</Button>
          </div>
        </Card>
      )}

      {/* Supplier list: only after category is selected */}
      <Card padding="lg">
        {!selectedCategory ? (
          <div className="py-12 text-center text-[#6b7280]">
            <p className="font-medium">Select a service category above</p>
            <p className="text-sm mt-1">Choose Movers, Housing, Schools, or another category to load and manage suppliers.</p>
          </div>
        ) : (
          <div className="border border-[#e5e7eb] rounded-lg overflow-hidden">
            {loading && suppliers.length === 0 ? (
              <div className="p-8 text-center text-[#6b7280]">Loading suppliers…</div>
            ) : suppliers.length === 0 ? (
              <div className="p-8 text-center text-[#6b7280]">
                <div className="text-sm font-medium">No suppliers in this category</div>
                <div className="text-xs mt-1">Try another category or add a supplier with a capability in {categoryLabel(selectedCategory)}.</div>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-[#f9fafb] border-b border-[#e5e7eb]">
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Name</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Service categories</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Coverage</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Status</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Verified</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliers.map((s) => (
                    <tr
                      key={s.id}
                      className="border-b border-[#e5e7eb] hover:bg-[#f9fafb] cursor-pointer"
                      onClick={() => goToDetail(s.id)}
                    >
                      <td className="py-3 px-4">
                        <span className="font-medium text-[#0b2b43]">{s.name}</span>
                        {s.legal_name && (
                          <span className="block text-xs text-[#6b7280]">{s.legal_name}</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-[#4b5563]">
                        {(s.service_categories || []).length
                          ? (s.service_categories || []).map(categoryLabel).join(', ')
                          : '-'}
                      </td>
                      <td className="py-3 px-4 text-[#4b5563] max-w-[220px]">
                        <span className="block truncate" title={s.coverage_summary || ''}>
                          {s.coverage_summary || '-'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs ${
                            s.status === 'active'
                              ? 'bg-green-100 text-green-800'
                              : s.status === 'draft'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {s.status}
                        </span>
                      </td>
                      <td className="py-3 px-4">{s.verified ? '✓' : '-'}</td>
                      <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
                        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Row actions">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => goToDetail(s.id)}
                            aria-label={`Edit ${s.name}`}
                          >
                            Edit
                          </Button>
                          {s.status === 'active' ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-amber-700 border-amber-300"
                              onClick={() => handleSetStatus(s.id, s.name, 'inactive')}
                              aria-label={`Deactivate ${s.name}`}
                            >
                              Deactivate
                            </Button>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-green-700 border-green-300"
                              onClick={() => handleSetStatus(s.id, s.name, 'active')}
                              aria-label={`Activate ${s.name}`}
                            >
                              Activate
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-[#4b5563]"
                            onClick={() => goToDetail(s.id, '#coverage')}
                            aria-label={`View coverage for ${s.name}`}
                          >
                            View coverage
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Card>
    </AdminLayout>
  );
};
