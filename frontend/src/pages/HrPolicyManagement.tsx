import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Card, Button, Alert, Input } from '../components/antigravity';
import { hrPolicyAPI } from '../api/client';
import { safeNavigate } from '../navigation/safeNavigate';

const BENEFIT_KEYS = [
  'preAssignmentVisit', 'travel', 'temporaryHousing', 'houseHunting', 'shipment',
  'storage', 'rentalAssistance', 'settlingInAllowance', 'visaImmigration',
  'taxAssistance', 'spousalSupport', 'educationSupport', 'languageTraining', 'repatriation',
];

const BENEFIT_LABELS: Record<string, string> = {
  preAssignmentVisit: 'Pre-Assignment Visit',
  travel: 'Travel',
  temporaryHousing: 'Temporary Housing',
  houseHunting: 'House Hunting',
  shipment: 'Shipment',
  storage: 'Storage',
  rentalAssistance: 'Rental Assistance',
  settlingInAllowance: 'Settling-In Allowance',
  visaImmigration: 'Visa & Immigration',
  taxAssistance: 'Tax Assistance',
  spousalSupport: 'Spousal Support',
  educationSupport: 'Education Support',
  languageTraining: 'Language Training',
  repatriation: 'Repatriation',
};

const DEFAULT_BENEFIT = {
  allowed: false,
  maxAllowed: { min: 0, medium: 0, extensive: 0, premium: 0 },
  unit: 'currency',
  currency: 'USD',
  documentationRequired: [] as string[],
  preApprovalRequired: false,
  notes: '',
};

function getDefaultPolicy() {
  const benefitCategories: Record<string, typeof DEFAULT_BENEFIT> = {};
  for (const k of BENEFIT_KEYS) {
    benefitCategories[k] = { ...DEFAULT_BENEFIT };
  }
  return {
    policyName: 'New Relocation Policy',
    companyEntity: '',
    effectiveDate: new Date().toISOString().slice(0, 10),
    expiryDate: null as string | null,
    status: 'draft' as const,
    employeeBands: ['Band1', 'Band2', 'Band3', 'Band4'],
    assignmentTypes: ['Permanent', 'Long-Term', 'Short-Term'],
    benefitCategories,
  };
}

export const HrPolicyManagement: React.FC = () => {
  const navigate = useNavigate();
  const [policies, setPolicies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState<'list' | 'create' | 'edit' | 'upload'>('list');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, any>>(getDefaultPolicy());
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadPolicies = useCallback(async () => {
    try {
      const { policies: list } = await hrPolicyAPI.list();
      setPolicies(list);
      setError('');
    } catch (err: any) {
      if (err?.response?.status === 401) {
        safeNavigate(navigate, 'landing');
        return;
      }
      setError('Failed to load policies');
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    loadPolicies();
  }, [loadPolicies]);

  const handleCreate = () => {
    setForm(getDefaultPolicy());
    setEditingId(null);
    setView('create');
  };

  const handleEdit = (policy: any) => {
    const id = policy.id || policy.policyId;
    setForm({
      policyName: policy.policyName || 'Untitled',
      companyEntity: policy.companyEntity || '',
      effectiveDate: policy.effectiveDate || new Date().toISOString().slice(0, 10),
      expiryDate: policy.expiryDate || null,
      status: policy._meta?.status || policy.status || 'draft',
      employeeBands: policy.employeeBands || ['Band1', 'Band2', 'Band3', 'Band4'],
      assignmentTypes: policy.assignmentTypes || ['Permanent', 'Long-Term', 'Short-Term'],
      benefitCategories: { ...getDefaultPolicy().benefitCategories, ...(policy.benefitCategories || {}) },
    });
    setEditingId(id);
    setView('edit');
  };

  const handleSave = async () => {
    setError('');
    try {
      const payload = {
        ...form,
        policyId: editingId || undefined,
        benefitCategories: form.benefitCategories,
      };
      if (editingId) {
        await hrPolicyAPI.update(editingId, payload);
      } else {
        await hrPolicyAPI.create(payload);
      }
      setView('list');
      loadPolicies();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save policy');
    }
  };

  const handlePublish = async () => {
    setError('');
    try {
      const payload = { ...form, status: 'published' };
      if (editingId) {
        await hrPolicyAPI.update(editingId, payload);
      } else {
        await hrPolicyAPI.create(payload);
      }
      setView('list');
      loadPolicies();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to publish policy');
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setError('');
    setUploading(true);
    try {
      await hrPolicyAPI.upload(uploadFile);
      setUploadFile(null);
      setView('list');
      loadPolicies();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const setBenefit = (key: string, field: string, value: any) => {
    setForm((prev) => {
      const cats = { ...(prev.benefitCategories || {}) };
      if (!cats[key]) cats[key] = { ...DEFAULT_BENEFIT };
      if (field === 'allowed') {
        cats[key] = { ...cats[key], allowed: !!value };
      } else if (field.startsWith('maxAllowed.')) {
        const tier = field.split('.')[1];
        cats[key] = {
          ...cats[key],
          maxAllowed: { ...(cats[key].maxAllowed || {}), [tier]: Number(value) || 0 },
        };
      } else {
        (cats[key] as any)[field] = value;
      }
      return { ...prev, benefitCategories: cats };
    });
  };

  if (loading) {
    return (
      <AppShell title="HR Policy Management" subtitle="Define and manage relocation policies.">
        <div className="text-center py-12 text-[#6b7280]">Loading policies...</div>
      </AppShell>
    );
  }

  return (
    <AppShell title="HR Policy Management" subtitle="Define, upload, and manage relocation policies. Published policies enable automatic criteria filling for employees.">
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      {view === 'list' && (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-3">
            <Button onClick={handleCreate}>Create policy</Button>
            <Button variant="outline" onClick={() => setView('upload')}>
              Upload policy (JSON/YAML)
            </Button>
            <Button variant="outline" onClick={() => safeNavigate(navigate, 'hrPolicy')}>
              View assignment policy
            </Button>
          </div>

          <Card padding="lg">
            <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Policies</h2>
            {policies.length === 0 ? (
              <p className="text-[#6b7280]">No policies yet. Create one or upload a JSON/YAML file.</p>
            ) : (
              <div className="space-y-2">
                {policies.map((p) => (
                  <div
                    key={p.id || p.policyId}
                    className="flex items-center justify-between p-4 border border-[#e2e8f0] rounded-lg hover:bg-[#f8fafc]"
                  >
                    <div>
                      <div className="font-medium text-[#0b2b43]">{p.policyName || 'Untitled'}</div>
                      <div className="text-sm text-[#6b7280]">
                        {p.companyEntity || '—'} · Effective {p.effectiveDate || '—'} · v{p._meta?.version ?? p.version ?? 1}
                        <span className={`ml-2 px-2 py-0.5 rounded text-xs ${p._meta?.status === 'published' ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-600'}`}>
                          {p._meta?.status || p.status || 'draft'}
                        </span>
                      </div>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => handleEdit(p)}>
                      Edit
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {view === 'upload' && (
        <Card padding="lg">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-2">Upload policy</h2>
          <p className="text-sm text-[#6b7280] mb-4">
            Upload a JSON or YAML file with the full policy structure. This enables automatic filling of service criteria for employees.
          </p>
          <div className="border-2 border-dashed border-[#e2e8f0] rounded-lg p-8 text-center">
            <input
              type="file"
              accept=".json,.yaml,.yml"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              className="hidden"
              id="policy-upload"
            />
            <label htmlFor="policy-upload" className="cursor-pointer text-[#0b2b43] hover:underline">
              {uploadFile ? uploadFile.name : 'Choose JSON or YAML file'}
            </label>
          </div>
          <div className="flex gap-3 mt-4">
            <Button onClick={handleUpload} disabled={!uploadFile || uploading}>
              {uploading ? 'Uploading...' : 'Upload'}
            </Button>
            <Button variant="outline" onClick={() => { setView('list'); setUploadFile(null); }}>
              Cancel
            </Button>
          </div>
        </Card>
      )}

      {(view === 'create' || view === 'edit') && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <button onClick={() => setView('list')} className="text-sm text-[#0b2b43] hover:underline">
              ← Back to list
            </button>
          </div>

          <Card padding="lg">
            <h3 className="font-semibold text-[#0b2b43] mb-4">Policy overview</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-[#0b2b43] mb-1">Policy name</label>
                <Input
                  value={form.policyName || ''}
                  onChange={(v) => setForm((p) => ({ ...p, policyName: v }))}
                  fullWidth
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#0b2b43] mb-1">Company entity</label>
                <Input
                  value={form.companyEntity || ''}
                  onChange={(v) => setForm((p) => ({ ...p, companyEntity: v }))}
                  fullWidth
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#0b2b43] mb-1">Effective date</label>
                <Input
                  type="date"
                  value={form.effectiveDate || ''}
                  onChange={(v) => setForm((p) => ({ ...p, effectiveDate: v }))}
                  fullWidth
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#0b2b43] mb-1">Assignment types</label>
                <div className="flex flex-wrap gap-2">
                  {['Permanent', 'Long-Term', 'Short-Term'].map((t) => (
                    <label key={t} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={(form.assignmentTypes || []).includes(t)}
                        onChange={(e) => {
                          const arr = [...(form.assignmentTypes || [])];
                          if (e.target.checked) arr.push(t);
                          else arr.splice(arr.indexOf(t), 1);
                          setForm((p) => ({ ...p, assignmentTypes: arr }));
                        }}
                      />
                      <span className="text-sm">{t}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          <Card padding="lg">
            <h3 className="font-semibold text-[#0b2b43] mb-2">Benefit definition matrix</h3>
            <p className="text-sm text-[#6b7280] mb-4">
              Toggle allowed and set max values per tier (min/medium/extensive/premium). Used for wizard auto-fill: temporaryHousing → housing budget, educationSupport → school budget, shipment → movers.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#e2e8f0]">
                    <th className="text-left py-2 pr-4">Benefit</th>
                    <th className="text-left py-2 pr-4">Allowed</th>
                    <th className="text-left py-2 px-2">Min</th>
                    <th className="text-left py-2 px-2">Medium</th>
                    <th className="text-left py-2 px-2">Extensive</th>
                    <th className="text-left py-2 px-2">Premium</th>
                    <th className="text-left py-2 pl-4">Pre-approval</th>
                  </tr>
                </thead>
                <tbody>
                  {BENEFIT_KEYS.map((key) => {
                    const b = form.benefitCategories?.[key] || { ...DEFAULT_BENEFIT };
                    const ma = b.maxAllowed || {};
                    return (
                      <tr key={key} className="border-b border-[#e2e8f0]">
                        <td className="py-2 pr-4 font-medium">{BENEFIT_LABELS[key] || key}</td>
                        <td className="py-2 pr-4">
                          <input
                            type="checkbox"
                            checked={!!b.allowed}
                            onChange={(e) => setBenefit(key, 'allowed', e.target.checked)}
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="number"
                            value={ma.min ?? 0}
                            onChange={(e) => setBenefit(key, 'maxAllowed.min', e.target.value)}
                            disabled={!b.allowed}
                            className="w-20 px-2 py-1 border rounded"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="number"
                            value={ma.medium ?? 0}
                            onChange={(e) => setBenefit(key, 'maxAllowed.medium', e.target.value)}
                            disabled={!b.allowed}
                            className="w-20 px-2 py-1 border rounded"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="number"
                            value={ma.extensive ?? 0}
                            onChange={(e) => setBenefit(key, 'maxAllowed.extensive', e.target.value)}
                            disabled={!b.allowed}
                            className="w-20 px-2 py-1 border rounded"
                          />
                        </td>
                        <td className="py-2 px-2">
                          <input
                            type="number"
                            value={ma.premium ?? 0}
                            onChange={(e) => setBenefit(key, 'maxAllowed.premium', e.target.value)}
                            disabled={!b.allowed}
                            className="w-20 px-2 py-1 border rounded"
                          />
                        </td>
                        <td className="py-2 pl-4">
                          <input
                            type="checkbox"
                            checked={!!b.preApprovalRequired}
                            onChange={(e) => setBenefit(key, 'preApprovalRequired', e.target.checked)}
                            disabled={!b.allowed}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="flex gap-3">
            <Button onClick={handleSave}>Save draft</Button>
            <Button variant="outline" onClick={handlePublish}>
              Publish (enable for employees)
            </Button>
            <Button variant="outline" onClick={() => setView('list')}>Cancel</Button>
          </div>
        </div>
      )}
    </AppShell>
  );
};
