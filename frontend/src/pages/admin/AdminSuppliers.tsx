import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card, Button, Alert } from '../../components/antigravity';
import { suppliersAPI } from '../../api/client';
import { ROUTE_DEFS } from '../../navigation/routes';

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
] as const;

export const AdminSuppliers: React.FC = () => {
  const navigate = useNavigate();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [serviceFilter, setServiceFilter] = useState<string>('');
  const [countryFilter, setCountryFilter] = useState<string>('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {};
      if (statusFilter) params.status = statusFilter;
      if (serviceFilter) params.service_category = serviceFilter;
      if (countryFilter) params.country_code = countryFilter;
      const res = await suppliersAPI.list(params);
      setSuppliers(res.suppliers || []);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : (err as Error)?.message;
      setError(String(msg || 'Failed to load suppliers'));
      setSuppliers([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, serviceFilter, countryFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <AdminLayout title="Supplier Registry" subtitle="Source of truth for recommendation matching and RFQ">
      <Card padding="lg">
        {error && (
          <Alert variant="error" className="mb-4">
            {error}
            <Button variant="outline" size="sm" className="ml-2" onClick={load}>
              Retry
            </Button>
          </Alert>
        )}

        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <Button onClick={() => navigate(ROUTE_DEFS.adminSuppliersNew.path)}>
            + Create supplier
          </Button>
        </div>
        <div className="flex flex-wrap gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Status</label>
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
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Service</label>
            <select
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
              className="border border-[#d1d5db] rounded px-3 py-2 text-sm"
            >
              <option value="">All</option>
              {SERVICE_CATEGORIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Country</label>
            <input
              type="text"
              value={countryFilter}
              onChange={(e) => setCountryFilter(e.target.value)}
              placeholder="e.g. SG"
              className="border border-[#d1d5db] rounded px-3 py-2 text-sm w-24"
            />
          </div>
          <div className="self-end">
            <Button onClick={load} disabled={loading}>
              {loading ? 'Loading...' : 'Refresh'}
            </Button>
          </div>
        </div>

        <div className="border border-[#e5e7eb] rounded-lg overflow-hidden">
          {loading && suppliers.length === 0 ? (
            <div className="p-8 text-center text-[#6b7280]">Loading suppliers...</div>
          ) : suppliers.length === 0 ? (
            <div className="p-8 text-center text-[#6b7280]">
              No suppliers found. Add suppliers via seed or API to see them here.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[#f9fafb] border-b border-[#e5e7eb]">
                  <th className="text-left py-3 px-4 font-medium text-[#374151]">Name</th>
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
                    onClick={() => navigate(ROUTE_DEFS.adminSuppliersDetail.path.replace(':id', s.id))}
                  >
                    <td className="py-3 px-4">
                      <span className="font-medium text-[#0b2b43]">{s.name}</span>
                      {s.legal_name && (
                        <span className="block text-xs text-[#6b7280]">{s.legal_name}</span>
                      )}
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
                    <td className="py-3 px-4">{s.verified ? '✓' : '—'}</td>
                    <td className="py-3 px-4" onClick={(ev) => ev.stopPropagation()}>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(ROUTE_DEFS.adminSuppliersDetail.path.replace(':id', s.id))}
                        >
                          Edit
                        </Button>
                        {s.status === 'active' ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-amber-700 border-amber-300"
                            onClick={() => {
                              if (window.confirm(`Deactivate ${s.name}? They will no longer appear in recommendations.`)) {
                                suppliersAPI.setStatus(s.id, 'inactive').then(load).catch(() => setError('Failed to deactivate'));
                              }
                            }}
                          >
                            Deactivate
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-green-700 border-green-300"
                            onClick={() => {
                              suppliersAPI.setStatus(s.id, 'active').then(load).catch(() => setError('Failed to activate'));
                            }}
                          >
                            Activate
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>
    </AdminLayout>
  );
};
