import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AppShell } from '../../../components/AppShell';
import { hrAPI } from '../../../api/client';
import type { CompanyProfilePayload } from '../../../types';
import { useHrCompanyContext } from '../../../contexts/HrCompanyContext';

// ── Option lists (mirror the prototype's static lists) ──────────────────────

const COUNTRIES: ReadonlyArray<{ code: string; name: string; flag: string }> = [
  { code: 'FR', name: 'France', flag: '🇫🇷' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'NO', name: 'Norway', flag: '🇳🇴' },
  { code: 'SE', name: 'Sweden', flag: '🇸🇪' },
  { code: 'FI', name: 'Finland', flag: '🇫🇮' },
  { code: 'DK', name: 'Denmark', flag: '🇩🇰' },
  { code: 'NL', name: 'Netherlands', flag: '🇳🇱' },
  { code: 'BE', name: 'Belgium', flag: '🇧🇪' },
  { code: 'IE', name: 'Ireland', flag: '🇮🇪' },
  { code: 'CH', name: 'Switzerland', flag: '🇨🇭' },
  { code: 'IT', name: 'Italy', flag: '🇮🇹' },
  { code: 'ES', name: 'Spain', flag: '🇪🇸' },
  { code: 'PT', name: 'Portugal', flag: '🇵🇹' },
  { code: 'AT', name: 'Austria', flag: '🇦🇹' },
  { code: 'PL', name: 'Poland', flag: '🇵🇱' },
  { code: 'US', name: 'United States', flag: '🇺🇸' },
  { code: 'CA', name: 'Canada', flag: '🇨🇦' },
  { code: 'MX', name: 'Mexico', flag: '🇲🇽' },
  { code: 'BR', name: 'Brazil', flag: '🇧🇷' },
  { code: 'JP', name: 'Japan', flag: '🇯🇵' },
  { code: 'KR', name: 'South Korea', flag: '🇰🇷' },
  { code: 'CN', name: 'China', flag: '🇨🇳' },
  { code: 'IN', name: 'India', flag: '🇮🇳' },
  { code: 'SG', name: 'Singapore', flag: '🇸🇬' },
  { code: 'AE', name: 'UAE', flag: '🇦🇪' },
  { code: 'AU', name: 'Australia', flag: '🇦🇺' },
  { code: 'NZ', name: 'New Zealand', flag: '🇳🇿' },
  { code: 'ZA', name: 'South Africa', flag: '🇿🇦' },
];

const INDUSTRIES = [
  'Technology', 'Financial Services', 'Professional Services',
  'Healthcare', 'Pharma / Biotech', 'Manufacturing', 'Retail',
  'Energy', 'Media & Entertainment', 'Non-profit', 'Government',
  'Education', 'Logistics', 'Other',
] as const;

const SIZE_BANDS = ['1–10', '11–50', '51–200', '201–500', '501–1000', '1001–5000', '5000+'] as const;

const WORKING_LOCATIONS = ['Remote', 'Hybrid', 'On-site', 'Office-first', 'Distributed'] as const;

const LOGO_ACCEPT = 'image/png,image/jpeg,image/jpg,image/svg+xml';
const LOGO_MAX_BYTES = 2 * 1024 * 1024;

// ── Form state shape (matches CompanyProfilePayload + UI-only fields) ───────

type FormState = {
  name: string;
  legal_name: string;
  industry: string;
  size_band: string;
  website: string;
  country: string;
  hq_city: string;
  address: string;
  phone: string;
  hr_contact: string;
  support_email: string;
  default_destination_country: string;
  default_working_location: string;
};

function emptyForm(): FormState {
  return {
    name: '', legal_name: '', industry: '', size_band: '', website: '',
    country: '', hq_city: '', address: '', phone: '',
    hr_contact: '', support_email: '',
    default_destination_country: '', default_working_location: '',
  };
}

function fromCompany(company: Record<string, unknown> | null): FormState {
  if (!company) return emptyForm();
  const pick = (snake: string, camel: string) =>
    String((company[snake] ?? company[camel] ?? '') || '').trim();
  return {
    name:                        pick('name', 'name'),
    legal_name:                  pick('legal_name', 'legalName'),
    industry:                    pick('industry', 'industry'),
    size_band:                   pick('size_band', 'sizeBand'),
    website:                     pick('website', 'website'),
    country:                     pick('country', 'country'),
    hq_city:                     pick('hq_city', 'hqCity'),
    address:                     pick('address', 'address'),
    phone:                       pick('phone', 'phone'),
    hr_contact:                  pick('hr_contact', 'hrContact'),
    support_email:               pick('support_email', 'supportEmail'),
    default_destination_country: pick('default_destination_country', 'defaultDestinationCountry'),
    default_working_location:    pick('default_working_location', 'defaultWorkingLocation'),
  };
}

function toPayload(f: FormState): CompanyProfilePayload {
  const trimOrUndef = (v: string): string | undefined => {
    const t = v.trim();
    return t === '' ? undefined : t;
  };
  return {
    name: f.name.trim(),
    country: trimOrUndef(f.country),
    size_band: trimOrUndef(f.size_band),
    address: trimOrUndef(f.address),
    phone: trimOrUndef(f.phone),
    hr_contact: trimOrUndef(f.hr_contact),
    legal_name: trimOrUndef(f.legal_name),
    website: trimOrUndef(f.website),
    hq_city: trimOrUndef(f.hq_city),
    industry: trimOrUndef(f.industry),
    default_destination_country: trimOrUndef(f.default_destination_country),
    support_email: trimOrUndef(f.support_email),
    default_working_location: trimOrUndef(f.default_working_location),
  };
}

// ── Main page ──────────────────────────────────────────────────────────────

export function CompanyProfileV2Page() {
  const { company, loading: contextLoading, error: contextError, refresh } = useHrCompanyContext();
  const [form, setForm] = useState<FormState>(emptyForm());
  const [pristine, setPristine] = useState<FormState>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const savedFlashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync form when context updates (initial load + after save/refresh).
  useEffect(() => {
    const next = fromCompany(company);
    setForm(next);
    setPristine(next);
  }, [company]);

  // Clean up the saved-flash timer on unmount.
  useEffect(() => () => {
    if (savedFlashTimer.current) clearTimeout(savedFlashTimer.current);
  }, []);

  const logoUrl = useMemo(() => {
    if (!company) return null;
    const v = (company['logo_url'] ?? (company as Record<string, unknown>)['logoUrl']) as string | undefined;
    return v ? String(v) : null;
  }, [company]);

  const isDirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(pristine), [form, pristine]);

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSave() {
    if (!form.name.trim()) {
      setSaveError('Name is required.');
      return;
    }
    setSaveError(null);
    setSaving(true);
    try {
      await hrAPI.saveCompanyProfile(toPayload(form));
      await refresh();
      setSavedFlash(true);
      if (savedFlashTimer.current) clearTimeout(savedFlashTimer.current);
      savedFlashTimer.current = setTimeout(() => setSavedFlash(false), 2500);
    } catch (e) {
      const err = e as { response?: { status?: number; data?: { detail?: string } }; message?: string };
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (detail) setSaveError(detail);
      else if (status === 500) setSaveError('Server crashed — check the uvicorn terminal for the Python traceback.');
      else if (status === 403) setSaveError('Permission denied — your HR/admin session may have expired.');
      else if (status === 422) setSaveError('The form data was rejected by the server (validation error).');
      else setSaveError(err?.message ?? 'Failed to save profile.');
    } finally {
      setSaving(false);
    }
  }

  function handleDiscard() {
    setForm(pristine);
    setSaveError(null);
  }

  const handleLogoFile = useCallback(
    async (file: File) => {
      setLogoError(null);
      if (!['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml'].includes(file.type)) {
        setLogoError('Use PNG, JPG, or SVG.');
        return;
      }
      if (file.size > LOGO_MAX_BYTES) {
        setLogoError('Logo must be 2MB or smaller.');
        return;
      }
      setLogoUploading(true);
      try {
        await hrAPI.uploadCompanyLogo(file);
        await refresh();
      } catch (e) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setLogoError(detail ?? 'Upload failed.');
      } finally {
        setLogoUploading(false);
      }
    },
    [refresh],
  );

  async function handleRemoveLogo() {
    if (!logoUrl) return;
    if (!window.confirm('Remove the current logo?')) return;
    setLogoError(null);
    setLogoUploading(true);
    try {
      await hrAPI.removeCompanyLogo();
      await refresh();
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setLogoError(detail ?? 'Remove failed.');
    } finally {
      setLogoUploading(false);
    }
  }

  // Completion score per section (lightweight — mirrors prototype's grouping).
  const completion = useMemo(() => {
    const filled = (...vs: string[]) => vs.filter((v) => v.trim()).length;
    const pct = (n: number, total: number) => (total === 0 ? 0 : Math.round((n / total) * 100));
    return {
      A: pct(filled(form.name, form.legal_name, form.industry, form.size_band, form.website), 5),
      B: pct(filled(form.country, form.hq_city, form.address, form.phone), 4),
      C: pct(filled(form.hr_contact, form.support_email, form.default_destination_country, form.default_working_location), 4),
      D: logoUrl ? 100 : 0,
    };
  }, [form, logoUrl]);

  return (
    <AppShell>
      <div className="mx-auto max-w-[1100px] px-6 py-6 pb-24">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
            ReloPass · /hr/company-profile
          </div>
          <div className="mt-1.5 flex items-baseline gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Company profile</h1>
            <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700 ring-1 ring-inset ring-indigo-200">
              v2 preview
            </span>
          </div>
          <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
            How your company appears across ReloPass — to your employees, your providers, and the platform's
            recommendation engine. Changes save against your tenant.
          </p>
        </div>

        {contextError && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {contextError}
          </div>
        )}

        {contextLoading && !company && (
          <div className="mb-4 text-sm text-slate-500">Loading profile…</div>
        )}

        {/* Section A — Identity */}
        <Section
          letter="A"
          title="Identity"
          subtitle="The name and category your tenant uses across the platform."
          completion={completion.A}
        >
          <Field label="Company name" required>
            <input
              value={form.name}
              onChange={(e) => setField('name', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="e.g. Aurora Energy"
            />
          </Field>
          <Field label="Legal name">
            <input
              value={form.legal_name}
              onChange={(e) => setField('legal_name', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="e.g. Aurora Energy AS"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Industry">
              <select
                value={form.industry}
                onChange={(e) => setField('industry', e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">—</option>
                {INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
            </Field>
            <Field label="Size band">
              <select
                value={form.size_band}
                onChange={(e) => setField('size_band', e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">—</option>
                {SIZE_BANDS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Website">
            <input
              value={form.website}
              onChange={(e) => setField('website', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="aurora-energy.com"
            />
          </Field>
        </Section>

        {/* Section B — Location & contact */}
        <Section
          letter="B"
          title="Location & contact"
          subtitle="Where your tenant is headquartered and how mobility teams can reach you."
          completion={completion.B}
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label="HQ country">
              <select
                value={form.country}
                onChange={(e) => setField('country', e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">—</option>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>{c.flag} {c.name}</option>
                ))}
              </select>
            </Field>
            <Field label="HQ city">
              <input
                value={form.hq_city}
                onChange={(e) => setField('hq_city', e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="e.g. Paris"
              />
            </Field>
          </div>
          <Field label="Address">
            <input
              value={form.address}
              onChange={(e) => setField('address', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Street, postcode, city"
            />
          </Field>
          <Field label="Phone">
            <input
              value={form.phone}
              onChange={(e) => setField('phone', e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="+33 …"
            />
          </Field>
        </Section>

        {/* Section C — HR & mobility defaults */}
        <Section
          letter="C"
          title="HR & mobility defaults"
          subtitle="Default routing for new relocation cases + the contacts ReloPass surfaces to your providers."
          completion={completion.C}
        >
          <div className="grid grid-cols-2 gap-3">
            <Field label="HR contact email">
              <input
                value={form.hr_contact}
                onChange={(e) => setField('hr_contact', e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="hr@company.com"
              />
            </Field>
            <Field label="Support email">
              <input
                value={form.support_email}
                onChange={(e) => setField('support_email', e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="mobility@company.com"
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Default destination country">
              <select
                value={form.default_destination_country}
                onChange={(e) => setField('default_destination_country', e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">—</option>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>{c.flag} {c.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Default working location">
              <select
                value={form.default_working_location}
                onChange={(e) => setField('default_working_location', e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">—</option>
                {WORKING_LOCATIONS.map((w) => <option key={w} value={w}>{w}</option>)}
              </select>
            </Field>
          </div>
        </Section>

        {/* Section D — Branding (logo only for now) */}
        <Section
          letter="D"
          title="Branding"
          subtitle="Logo your employees and providers see across the platform."
          completion={completion.D}
        >
          <div className="flex items-center gap-4">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
              {logoUrl ? (
                <img src={logoUrl} alt="Company logo" className="h-full w-full object-contain" />
              ) : (
                <span className="text-[11px] text-slate-400">No logo</span>
              )}
            </div>
            <div className="space-y-2">
              <input
                ref={fileInputRef}
                type="file"
                accept={LOGO_ACCEPT}
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleLogoFile(f);
                  e.target.value = '';
                }}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={logoUploading}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {logoUploading ? 'Uploading…' : logoUrl ? 'Replace logo' : 'Upload logo'}
                </button>
                {logoUrl && (
                  <button
                    type="button"
                    onClick={() => void handleRemoveLogo()}
                    disabled={logoUploading}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    Remove
                  </button>
                )}
              </div>
              <p className="text-[11px] text-slate-500">PNG, JPG, or SVG. Max 2 MB.</p>
              {logoError && (
                <p className="text-[11px] text-rose-600">{logoError}</p>
              )}
            </div>
          </div>
        </Section>
      </div>

      {/* Sticky save bar — appears when the form is dirty */}
      {isDirty && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 backdrop-blur-md">
          <div className="mx-auto flex max-w-[1100px] items-center justify-between gap-3 px-6 py-3">
            <div className="text-[13px] text-slate-600">
              {savedFlash ? (
                <span className="text-emerald-700">✓ Saved.</span>
              ) : saveError ? (
                <span className="text-rose-700">{saveError}</span>
              ) : (
                <span>You have unsaved changes.</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleDiscard}
                disabled={saving}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Always-visible saved flash when form is pristine */}
      {!isDirty && savedFlash && (
        <div className="fixed bottom-6 right-6 z-30 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-lg">
          ✓ Saved
        </div>
      )}
    </AppShell>
  );
}

// ── Visual primitives ──────────────────────────────────────────────────────

function Section({
  letter,
  title,
  subtitle,
  completion,
  children,
}: {
  letter: string;
  title: string;
  subtitle: string;
  completion: number;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded bg-slate-900 text-[11px] font-semibold text-white">
              {letter}
            </span>
            <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>
          </div>
          <p className="mt-1 text-[12.5px] text-slate-500">{subtitle}</p>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Section</div>
          <div className="mt-0.5 text-[13px] font-semibold tabular-nums text-slate-700">{completion}%</div>
          <div className="mt-1 h-1 w-20 overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full ${completion === 100 ? 'bg-emerald-500' : completion >= 50 ? 'bg-indigo-500' : 'bg-slate-300'}`}
              style={{ width: `${completion}%` }}
            />
          </div>
        </div>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
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

export default CompanyProfileV2Page;
