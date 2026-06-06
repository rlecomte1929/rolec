import { useEffect, useState } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
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
      const err = e as {
        response?: { status?: number; data?: { detail?: string } };
        message?: string;
      };
      const status = err?.response?.status;
      const serverDetail = err?.response?.data?.detail;
      const action = mode === 'create' ? 'create' : 'update';
      // Server-supplied detail wins; otherwise infer from HTTP status; finally
      // fall back to the raw axios message. 500 gets a hint about backend logs
      // since the modal can't surface a meaningful reason without it.
      let detail: string;
      if (serverDetail) {
        detail = serverDetail;
      } else if (status === 500) {
        detail = `Server crashed while trying to ${action} the company. Check the uvicorn terminal for the Python traceback.`;
      } else if (status === 403) {
        detail = `Permission denied — your admin session may have expired.`;
      } else if (status === 422) {
        detail = `The form data was rejected by the server (validation error).`;
      } else if (status) {
        detail = `Server returned ${status} — could not ${action} company.`;
      } else {
        detail = err?.message ?? `Failed to ${action} company`;
      }
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
          <Button unstyled
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            ✕
          </Button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-6 py-5">
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <Field label="Name" required>
            <Input unstyled
              value={form.name}
              onChange={(v) => setField('name', v)}
              placeholder="Company name"
              autoFocus
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
          </Field>

          <Field label="Country">
            <Input unstyled
              value={form.country}
              onChange={(v) => setField('country', v)}
              placeholder="e.g. Norway"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
          </Field>

          <Field label="Size band">
            <Input unstyled
              value={form.size_band}
              onChange={(v) => setField('size_band', v)}
              placeholder="e.g. 50–200"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Plan tier">
              <select
                value={form.plan_tier}
                onChange={(e) => setField('plan_tier', e.target.value as CompanyV2PlanTier)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
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
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="archived">Archived</option>
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="HR seat limit">
              <Input unstyled
                type="number"
                min={0}
                value={form.hr_seat_limit}
                onChange={(v) => setField('hr_seat_limit', v)}
                placeholder="—"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
              />
            </Field>
            <Field label="Employee seat limit">
              <Input unstyled
                type="number"
                min={0}
                value={form.employee_seat_limit}
                onChange={(v) => setField('employee_seat_limit', v)}
                placeholder="—"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
              />
            </Field>
          </div>

          <Field label="Address">
            <Input unstyled
              value={form.address}
              onChange={(v) => setField('address', v)}
              placeholder="Street, city, postcode"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Phone">
              <Input unstyled
                value={form.phone}
                onChange={(v) => setField('phone', v)}
                placeholder="+33 …"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
              />
            </Field>
            <Field label="HR contact email">
              <Input unstyled
                value={form.hr_contact}
                onChange={(v) => setField('hr_contact', v)}
                placeholder="hr@company.com"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
              />
            </Field>
          </div>

          <Field label="Support email">
            <Input unstyled
              value={form.support_email}
              onChange={(v) => setField('support_email', v)}
              placeholder="support@company.com"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent-500"
            />
          </Field>

          <div className="flex justify-end gap-2 pt-2">
            <Button unstyled
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </Button>
            <Button unstyled
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {submitting ? 'Saving…' : mode === 'create' ? 'Add tenant' : 'Save changes'}
            </Button>
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
