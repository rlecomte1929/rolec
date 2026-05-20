import { useEffect, useState } from 'react';
import { adminAPI } from '../../../api/client';
import type { CompanyV2, CompanyV2PlanTier, CompanyV2Status } from './adapter';

/**
 * Single modal that handles both "Add company" and "Edit company".
 *
 * - `mode === 'create'` → empty form, submits via adminAPI.createCompany
 * - `mode === 'edit'`   → form prefilled from `initial`, submits via
 *                          adminAPI.updateCompany(initial.id, …)
 *
 * `onSaved` fires only after a successful API call so the parent can
 * trigger a refetch of the list.
 */

type FormPayload = {
  name: string;
  country: string;
  size_band: string;
  plan_tier: CompanyV2PlanTier;
  status: CompanyV2Status;
  hr_seat_limit: string;
  employee_seat_limit: string;
  address: string;
  phone: string;
  hr_contact: string;
  support_email: string;
};

function emptyForm(): FormPayload {
  return {
    name: '',
    country: '',
    size_band: '',
    plan_tier: 'low',
    status: 'active',
    hr_seat_limit: '',
    employee_seat_limit: '',
    address: '',
    phone: '',
    hr_contact: '',
    support_email: '',
  };
}

function formFromCompany(c: CompanyV2): FormPayload {
  return {
    name: c.name,
    country: c.country ?? '',
    size_band: c.size_band ?? '',
    plan_tier: c.plan_tier,
    status: c.status,
    hr_seat_limit: c.hr_seat_limit == null ? '' : String(c.hr_seat_limit),
    employee_seat_limit: c.employee_seat_limit == null ? '' : String(c.employee_seat_limit),
    address: c.address ?? '',
    phone: c.phone ?? '',
    hr_contact: c.hr_contact ?? '',
    support_email: c.support_email ?? '',
  };
}

interface CompanyFormModalProps {
  mode: 'create' | 'edit';
  initial?: CompanyV2;
  onClose: () => void;
  onSaved: () => void;
}

export function CompanyFormModal({ mode, initial, onClose, onSaved }: CompanyFormModalProps) {
  const [form, setForm] = useState<FormPayload>(() =>
    initial ? formFromCompany(initial) : emptyForm(),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-sync if the parent swaps the edit target while the modal is open.
  useEffect(() => {
    setForm(initial ? formFromCompany(initial) : emptyForm());
    setError(null);
  }, [initial]);

  function setField<K extends keyof FormPayload>(key: K, value: FormPayload[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function buildApiPayload(): {
    name?: string;
    country?: string;
    size_band?: string;
    plan_tier?: string;
    status?: string;
    hr_seat_limit?: number;
    employee_seat_limit?: number;
    address?: string;
    phone?: string;
    hr_contact?: string;
    support_email?: string;
  } {
    const payload: Record<string, unknown> = {};
    const trimmedName = form.name.trim();
    if (trimmedName) payload.name = trimmedName;
    if (form.country.trim()) payload.country = form.country.trim();
    if (form.size_band.trim()) payload.size_band = form.size_band.trim();
    payload.plan_tier = form.plan_tier;
    payload.status = form.status;
    if (form.hr_seat_limit !== '') payload.hr_seat_limit = Number(form.hr_seat_limit);
    if (form.employee_seat_limit !== '') payload.employee_seat_limit = Number(form.employee_seat_limit);
    if (form.address.trim()) payload.address = form.address.trim();
    if (form.phone.trim()) payload.phone = form.phone.trim();
    if (form.hr_contact.trim()) payload.hr_contact = form.hr_contact.trim();
    if (form.support_email.trim()) payload.support_email = form.support_email.trim();
    return payload;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = form.name.trim();
    if (!trimmedName) {
      setError('Name is required');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const payload = buildApiPayload();
      if (mode === 'create') {
        // createCompany requires `name` to be present.
        await adminAPI.createCompany({ ...payload, name: trimmedName });
      } else if (initial) {
        await adminAPI.updateCompany(initial.id, payload);
      }
      onSaved();
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (e as Error)?.message ??
        `Failed to ${mode === 'create' ? 'create' : 'update'} company`;
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-900">
            {mode === 'create' ? 'Add tenant' : `Edit ${initial?.name ?? 'company'}`}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-6 py-5">
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <Field label="Name" required>
            <input
              value={form.name}
              onChange={(e) => setField('name', e.target.value)}
              placeholder="Company name"
              autoFocus
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </Field>

          <Field label="Country">
            <input
              value={form.country}
              onChange={(e) => setField('country', e.target.value)}
              placeholder="e.g. Norway"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </Field>

          <Field label="Size band">
            <input
              value={form.size_band}
              onChange={(e) => setField('size_band', e.target.value)}
              placeholder="e.g. 50–200"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Plan tier">
              <select
                value={form.plan_tier}
                onChange={(e) => setField('plan_tier', e.target.value as CompanyV2PlanTier)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="premium">Premium</option>
              </select>
            </Field>
            <Field label="Status">
              <select
                value={form.status}
                onChange={(e) => setField('status', e.target.value as CompanyV2Status)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="archived">Archived</option>
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="HR seat limit">
              <input
                type="number"
                min={0}
                value={form.hr_seat_limit}
                onChange={(e) => setField('hr_seat_limit', e.target.value)}
                placeholder="—"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </Field>
            <Field label="Employee seat limit">
              <input
                type="number"
                min={0}
                value={form.employee_seat_limit}
                onChange={(e) => setField('employee_seat_limit', e.target.value)}
                placeholder="—"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </Field>
          </div>

          <Field label="Address">
            <input
              value={form.address}
              onChange={(e) => setField('address', e.target.value)}
              placeholder="Street, city, postcode"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Phone">
              <input
                value={form.phone}
                onChange={(e) => setField('phone', e.target.value)}
                placeholder="+33 …"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </Field>
            <Field label="HR contact email">
              <input
                value={form.hr_contact}
                onChange={(e) => setField('hr_contact', e.target.value)}
                placeholder="hr@company.com"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </Field>
          </div>

          <Field label="Support email">
            <input
              value={form.support_email}
              onChange={(e) => setField('support_email', e.target.value)}
              placeholder="support@company.com"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </Field>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {submitting ? 'Saving…' : mode === 'create' ? 'Add tenant' : 'Save changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  required = false,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
        {label} {required && <span className="text-rose-600">*</span>}
      </div>
      {children}
    </label>
  );
}

export default CompanyFormModal;
