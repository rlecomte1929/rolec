import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CompanyProfilePayload } from '../../../types';

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

const WORKING_LOCATIONS: ReadonlyArray<{ value: string; icon: string }> = [
  { value: 'Remote', icon: '🌍' },
  { value: 'Hybrid', icon: '🏢' },
  { value: 'On-site', icon: '🏬' },
  { value: 'Office-first', icon: '🏛️' },
  { value: 'Distributed', icon: '🌐' },
];

const LOGO_ACCEPT = 'image/png,image/jpeg,image/jpg,image/svg+xml';
const LOGO_MAX_BYTES = 2 * 1024 * 1024;

const AUTOSAVE_DEBOUNCE_MS = 1500;

// ── Form state shape (matches CompanyProfilePayload) ────────────────────────

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

type SectionKey = 'identity' | 'location' | 'hr' | 'branding';

function emptyForm(): FormState {
  return {
    name: '', legal_name: '', industry: '', size_band: '', website: '',
    country: '', hq_city: '', address: '', phone: '',
    hr_contact: '', support_email: '',
    default_destination_country: '', default_working_location: '',
  };
}

/** Adapter: nested record (snake or camel) → flat form state. */
export function formFromCompany(company: Record<string, unknown> | null): FormState {
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

/** Adapter: flat form state → CompanyProfilePayload (drops empty strings). */
export function formToPayload(f: FormState): CompanyProfilePayload {
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

// ── Props ───────────────────────────────────────────────────────────────────

export interface CompanyProfileFormProps {
  /** Source company record (snake or camel). Used to seed + reset form state. */
  company: Record<string, unknown> | null;
  /** True while the source data is being fetched. */
  loading?: boolean;
  /** Error from the data-fetch layer (above the form). */
  loadError?: string | null;
  /** Persist the form. Must return a promise that resolves on success. */
  onSave: (payload: CompanyProfilePayload) => Promise<void>;
  /** Optional logo upload handler. If absent, the upload button is hidden. */
  onUploadLogo?: (file: File) => Promise<void>;
  /** Optional logo remove handler. If absent, the remove button is hidden. */
  onRemoveLogo?: () => Promise<void>;
  /** Eyebrow path shown above the h1. */
  eyebrow: string;
  /** Main heading. */
  title: string;
  /** One-line description shown below the h1. */
  subtitle: string;
  /** Optional badge text shown next to the h1. */
  badge?: string;
  /** Optional content rendered at the very top, before the page header. */
  topSlot?: React.ReactNode;
  /** Path the "Back" button navigates to. Defaults to /hr/dashboard. */
  backTo?: string;
  /** Label for the back button. Defaults to "Back to Dashboard". */
  backLabel?: string;
}

// ── Component ──────────────────────────────────────────────────────────────

export function CompanyProfileForm({
  company,
  loading = false,
  loadError = null,
  onSave,
  onUploadLogo,
  onRemoveLogo,
  eyebrow,
  title,
  subtitle,
  badge,
  topSlot,
  backTo = '/hr/dashboard',
  backLabel = 'Back to Dashboard',
}: CompanyProfileFormProps) {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>(() => formFromCompany(company));
  const [pristine, setPristine] = useState<FormState>(() => formFromCompany(company));
  const [savedSnapshot, setSavedSnapshot] = useState<FormState>(() => formFromCompany(company));
  const [saving, setSaving] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [sectionFlash, setSectionFlash] = useState<Record<SectionKey, boolean>>({
    identity: false, location: false, hr: false, branding: false,
  });
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flashTimers = useRef<Record<SectionKey, ReturnType<typeof setTimeout> | null>>({
    identity: null, location: null, hr: null, branding: null,
  });

  // Re-seed when source company changes
  useEffect(() => {
    const next = formFromCompany(company);
    setForm(next);
    setPristine(next);
    setSavedSnapshot(next);
  }, [company]);

  // Cleanup timers on unmount
  useEffect(() => () => {
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    Object.values(flashTimers.current).forEach((t) => t && clearTimeout(t));
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

  // Which sections changed since the last successful save
  const sectionDirty = useMemo<Record<SectionKey, boolean>>(() => {
    const diff = (k: keyof FormState) => form[k] !== savedSnapshot[k];
    return {
      identity: diff('name') || diff('legal_name') || diff('industry') || diff('size_band') || diff('website'),
      location: diff('country') || diff('hq_city') || diff('address') || diff('phone'),
      hr: diff('hr_contact') || diff('support_email') || diff('default_destination_country') || diff('default_working_location'),
      branding: false,
    };
  }, [form, savedSnapshot]);

  function flashSection(key: SectionKey) {
    setSectionFlash((s) => ({ ...s, [key]: true }));
    if (flashTimers.current[key]) clearTimeout(flashTimers.current[key]!);
    flashTimers.current[key] = setTimeout(() => {
      setSectionFlash((s) => ({ ...s, [key]: false }));
    }, 2200);
  }

  const persist = useCallback(
    async (snapshot: FormState, sourceSections: SectionKey[]) => {
      if (!snapshot.name.trim()) {
        setSaveError('Company name is required.');
        return false;
      }
      setSaveError(null);
      setSaving(true);
      try {
        await onSave(formToPayload(snapshot));
        setSavedSnapshot(snapshot);
        setPristine(snapshot);
        setLastSavedAt(Date.now());
        sourceSections.forEach((k) => flashSection(k));
        return true;
      } catch (e) {
        const err = e as { response?: { status?: number; data?: { detail?: string } }; message?: string };
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail;
        if (detail) setSaveError(detail);
        else if (status === 500) setSaveError('Server error — check the uvicorn terminal for the Python traceback.');
        else if (status === 403) setSaveError('Permission denied — your session may have expired.');
        else if (status === 422) setSaveError('The form data was rejected by the server (validation error).');
        else setSaveError(err?.message ?? 'Failed to save profile.');
        return false;
      } finally {
        setSaving(false);
      }
    },
    [onSave],
  );

  // Debounced auto-save: schedule a save 1.5s after the last edit (when dirty)
  useEffect(() => {
    if (!isDirty) return;
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    const snapshot = form;
    const sections = (Object.keys(sectionDirty) as SectionKey[]).filter((k) => sectionDirty[k]);
    autosaveTimer.current = setTimeout(() => {
      void persist(snapshot, sections);
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form, isDirty]);

  async function handleManualSave() {
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    const sections = (Object.keys(sectionDirty) as SectionKey[]).filter((k) => sectionDirty[k]);
    await persist(form, sections.length ? sections : ['identity', 'location', 'hr']);
  }

  const handleLogoFile = useCallback(
    async (file: File) => {
      if (!onUploadLogo) return;
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
        await onUploadLogo(file);
        flashSection('branding');
        setLastSavedAt(Date.now());
      } catch (e) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setLogoError(detail ?? 'Upload failed.');
      } finally {
        setLogoUploading(false);
      }
    },
    [onUploadLogo],
  );

  async function handleRemoveLogo() {
    if (!onRemoveLogo || !logoUrl) return;
    if (!window.confirm('Remove the current logo?')) return;
    setLogoError(null);
    setLogoUploading(true);
    try {
      await onRemoveLogo();
      flashSection('branding');
      setLastSavedAt(Date.now());
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setLogoError(detail ?? 'Remove failed.');
    } finally {
      setLogoUploading(false);
    }
  }

  const savedAgo = useRelativeTime(lastSavedAt);

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-6 pb-28">
      {topSlot}

      <div className="mb-5">
        <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">{eyebrow}</div>
        <div className="mt-1.5 flex items-baseline gap-3">
          <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">{title}</h1>
          {badge && (
            <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700 ring-1 ring-inset ring-indigo-200">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-1 max-w-3xl text-[13px] text-slate-500">{subtitle}</p>
      </div>

      {loadError && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {loadError}
        </div>
      )}

      {loading && !company && (
        <div className="mb-4 text-sm text-slate-500">Loading profile…</div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* ── Company identity ──────────────────────────────────────────── */}
        <SectionCard
          title="Company identity"
          subtitle="How your company is identified across ReloPass."
          savedFlash={sectionFlash.identity}
          dirty={sectionDirty.identity}
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field
              label="Company name"
              required
              helper="Used as the employer name on new relocation cases."
            >
              <input
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                className={inputCx}
                placeholder="e.g. Aurora Energy"
              />
            </Field>
            <Field
              label="Legal name"
              helper="Used on official case documents and contracts."
            >
              <input
                value={form.legal_name}
                onChange={(e) => setField('legal_name', e.target.value)}
                className={inputCx}
                placeholder="e.g. Aurora Energy AS"
              />
            </Field>
            <Field label="Industry">
              <select
                value={form.industry}
                onChange={(e) => setField('industry', e.target.value)}
                className={selectCx}
              >
                <option value="">—</option>
                {INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
            </Field>
            <Field
              label="Company size band"
              helper="Used for filtering & may affect policy tier eligibility."
            >
              <select
                value={form.size_band}
                onChange={(e) => setField('size_band', e.target.value)}
                className={selectCx}
              >
                <option value="">—</option>
                {SIZE_BANDS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Website" full>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[12.5px] text-slate-400">
                  https://
                </span>
                <input
                  value={form.website}
                  onChange={(e) => setField('website', e.target.value.replace(/^https?:\/\//, ''))}
                  className={`${inputCx} pl-[60px]`}
                  placeholder="aurora-energy.com"
                />
              </div>
            </Field>
          </div>
        </SectionCard>

        {/* ── Location & contact ────────────────────────────────────────── */}
        <SectionCard
          title="Location & contact"
          subtitle="Where your company is based and how to reach you."
          savedFlash={sectionFlash.location}
          dirty={sectionDirty.location}
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field
              label="Country of incorporation"
              helper="Pre-filled as employer country in every new relocation case."
            >
              <CountrySelect
                value={form.country}
                onChange={(v) => setField('country', v)}
              />
            </Field>
            <Field label="HQ city">
              <input
                value={form.hq_city}
                onChange={(e) => setField('hq_city', e.target.value)}
                className={inputCx}
                placeholder="Paris"
              />
            </Field>
            <Field label="Address" full>
              <input
                value={form.address}
                onChange={(e) => setField('address', e.target.value)}
                className={inputCx}
                placeholder="12 Avenue de Friedland, 75008 Paris, France"
              />
            </Field>
            <Field
              label="Phone"
              full
              helper="International format with country code."
            >
              <input
                value={form.phone}
                onChange={(e) => setField('phone', e.target.value)}
                className={inputCx}
                placeholder="+33 1 4502 8821"
              />
            </Field>
          </div>
        </SectionCard>

        {/* ── HR & mobility defaults ────────────────────────────────────── */}
        <SectionCard
          title="HR & mobility defaults"
          subtitle="These defaults power your relocation cases and policy engine."
          savedFlash={sectionFlash.hr}
          dirty={sectionDirty.hr}
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field
              label="HR contact"
              helper="Internal — used in audit logs and admin views."
            >
              <input
                value={form.hr_contact}
                onChange={(e) => setField('hr_contact', e.target.value)}
                className={inputCx}
                placeholder="helena.muller@aurora-energy.com"
              />
            </Field>
            <Field label="Support email">
              <input
                value={form.support_email}
                onChange={(e) => setField('support_email', e.target.value)}
                className={inputCx}
                placeholder="mobility@aurora-energy.com"
              />
              <InfoBanner>
                <span className="font-medium">Employees see this</span> as their HR contact in the relocation portal.
              </InfoBanner>
            </Field>
            <Field label="Default destination country">
              <CountrySelect
                value={form.default_destination_country}
                onChange={(v) => setField('default_destination_country', v)}
              />
              <InfoBanner>
                Seeds the destination picker in <span className="font-medium">every new case</span> and drives supplier &amp; resource recommendations.
              </InfoBanner>
            </Field>
            <Field label="Default working location">
              <select
                value={form.default_working_location}
                onChange={(e) => setField('default_working_location', e.target.value)}
                className={selectCx}
              >
                <option value="">—</option>
                {WORKING_LOCATIONS.map((w) => (
                  <option key={w.value} value={w.value}>{w.icon}  {w.value}</option>
                ))}
              </select>
              <InfoBanner>
                Injected into the <span className="font-medium">policy evaluation engine</span> — affects which policies are triggered for each case.
              </InfoBanner>
            </Field>
          </div>
        </SectionCard>

        {/* ── Branding ──────────────────────────────────────────────────── */}
        <SectionCard
          title="Branding"
          subtitle="Your logo and colours appear across the entire platform."
          savedFlash={sectionFlash.branding}
          dirty={false}
        >
          <div className="flex items-start gap-4">
            <div className="flex h-32 w-32 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white">
              {logoUrl ? (
                <img src={logoUrl} alt="Company logo" className="h-full w-full object-contain" />
              ) : (
                <span className="text-[11px] text-slate-400">No logo</span>
              )}
            </div>
            <div className="flex-1 space-y-3">
              <div>
                <div className="text-[13.5px] font-semibold text-slate-900">Company logo</div>
                <p className="mt-0.5 text-[12px] text-slate-500">
                  PNG, JPG or SVG · max 2 MB · square 512×512 recommended for best quality.
                </p>
              </div>
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
              <div className="flex flex-wrap gap-2">
                {onUploadLogo ? (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={logoUploading}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-[12.5px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    <UploadIcon className="h-3.5 w-3.5" />
                    {logoUploading ? 'Uploading…' : logoUrl ? 'Replace' : 'Upload logo'}
                  </button>
                ) : (
                  <span className="text-[11px] text-slate-400">
                    Logo upload is only available to HR for their own company.
                  </span>
                )}
                {onRemoveLogo && logoUrl && (
                  <button
                    type="button"
                    onClick={() => void handleRemoveLogo()}
                    disabled={logoUploading}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-[12.5px] font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                  >
                    <span aria-hidden>×</span> Remove
                  </button>
                )}
              </div>
              {logoError && <p className="text-[11px] text-rose-600">{logoError}</p>}
              <InfoBanner>
                <span className="font-medium">Your logo appears in the header</span> on every page of the platform, visible to both HR managers and employees.
              </InfoBanner>
            </div>
          </div>
        </SectionCard>
      </div>

      {/* Sticky bottom bar — sits within the main scroll column so the
          PlatformSidebar isn't covered when it's expanded. Uses brand
          navy (#0b2b43) + teal (#1f8e8b) to match the antigravity Button
          primary/secondary variants used across the rest of the platform. */}
      <div className="sticky bottom-0 left-0 right-0 z-20 -mx-6 mt-6 border-t border-[#e2e8f0] bg-white/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-6 py-3">
          <div className="flex items-center gap-3 text-[13px]">
            {saveError ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1 text-rose-700 ring-1 ring-inset ring-rose-200">
                <span aria-hidden>⚠</span> {saveError}
              </span>
            ) : saving ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#e6f2f4] px-3 py-1 text-[#0b2b43] ring-1 ring-inset ring-[#cfe3e6]">
                <Spinner className="h-3 w-3" /> Saving…
              </span>
            ) : isDirty ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-amber-800 ring-1 ring-inset ring-amber-200">
                Unsaved changes
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-emerald-800 ring-1 ring-inset ring-emerald-200">
                <CheckIcon className="h-3 w-3" /> All changes saved
              </span>
            )}
            {lastSavedAt && !isDirty && !saving && (
              <span className="text-[#64748b]">Auto-saved {savedAgo}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => navigate(backTo)}
              className="inline-flex items-center gap-1.5 rounded-lg border-2 border-[#0b2b43] bg-white px-4 py-2 text-[13px] font-medium text-[#0b2b43] transition-colors hover:bg-[#e6f2f4] focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-2"
            >
              <span aria-hidden>←</span> {backLabel}
            </button>
            <button
              type="button"
              onClick={() => void handleManualSave()}
              disabled={saving || !form.name.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#0b2b43] px-4 py-2 text-[13px] font-medium text-white shadow-sm transition-colors hover:bg-[#123651] focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <CheckIcon className="h-3.5 w-3.5" /> Save profile
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Visual primitives ──────────────────────────────────────────────────────

const inputCx =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-[13.5px] text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100';

const selectCx =
  'w-full appearance-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-[13.5px] text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100';

function SectionCard({
  title,
  subtitle,
  savedFlash,
  dirty,
  children,
}: {
  title: string;
  subtitle: string;
  savedFlash: boolean;
  dirty: boolean;
  children: React.ReactNode;
}) {
  // Show pill: green "Saved" by default; emerald flash when section just saved; amber "Editing" if dirty.
  let pill: React.ReactNode;
  if (savedFlash) {
    pill = (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800 ring-1 ring-inset ring-emerald-200">
        <CheckIcon className="h-3 w-3" /> Saved
      </span>
    );
  } else if (dirty) {
    pill = (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800 ring-1 ring-inset ring-amber-200">
        Editing
      </span>
    );
  } else {
    pill = (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
        <CheckIcon className="h-3 w-3" /> Saved
      </span>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <span
            className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded-full ${
              dirty ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
            }`}
            aria-hidden
          >
            <CheckIcon className="h-3 w-3" />
          </span>
          <div>
            <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>
            <p className="mt-0.5 text-[12.5px] text-slate-500">{subtitle}</p>
          </div>
        </div>
        <div className="shrink-0">{pill}</div>
      </div>
      <div>{children}</div>
    </section>
  );
}

function Field({
  label,
  required = false,
  helper,
  full = false,
  children,
}: {
  label: string;
  required?: boolean;
  helper?: string;
  full?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className={`block ${full ? 'md:col-span-2' : ''}`}>
      <div className="mb-1 text-[12px] font-medium text-slate-700">
        {label} {required && <span className="text-rose-600">*</span>}
      </div>
      {children}
      {helper && <p className="mt-1 text-[11.5px] text-slate-500">{helper}</p>}
    </label>
  );
}

function InfoBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-2 inline-flex w-full items-start gap-1.5 rounded-md bg-indigo-50/70 px-2.5 py-1.5 text-[11.5px] text-indigo-900 ring-1 ring-inset ring-indigo-100">
      <InfoIcon className="mt-0.5 h-3 w-3 shrink-0 text-indigo-500" />
      <span>{children}</span>
    </div>
  );
}

function CountrySelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const selected = COUNTRIES.find((c) => c.code === value);
  return (
    <div className="relative">
      {selected && (
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[14px]">
          {selected.flag}
        </span>
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${selectCx} ${selected ? 'pl-9' : ''}`}
      >
        <option value="">—</option>
        {COUNTRIES.map((c) => (
          <option key={c.code} value={c.code}>{c.flag} {c.name}</option>
        ))}
      </select>
    </div>
  );
}

// ── Icons (tiny inline SVGs to avoid a new dependency) ─────────────────────

function CheckIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
      <path d="M2 6.5l2.5 2.5L10 3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function InfoIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <circle cx="6" cy="6" r="5" />
      <path d="M6 5.5v3M6 3.5v.01" strokeLinecap="round" />
    </svg>
  );
}

function UploadIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="M7 9V2M4 5l3-3 3 3M2 11h10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Spinner({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`animate-spin ${className}`} fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
      <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

// ── Hooks ──────────────────────────────────────────────────────────────────

function useRelativeTime(ts: number | null): string {
  const [, force] = useState(0);
  useEffect(() => {
    if (!ts) return;
    const id = setInterval(() => force((n) => n + 1), 5000);
    return () => clearInterval(id);
  }, [ts]);
  if (!ts) return '';
  const seconds = Math.max(1, Math.round((Date.now() - ts) / 1000));
  if (seconds < 60) return `${seconds} second${seconds === 1 ? '' : 's'} ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.round(minutes / 60);
  return `${hours} hour${hours === 1 ? '' : 's'} ago`;
}

export default CompanyProfileForm;
