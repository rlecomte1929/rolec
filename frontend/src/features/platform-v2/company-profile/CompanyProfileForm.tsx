import { useCallback, useEffect, useRef, useState } from 'react';
import { Controller } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { FileInput } from '../../../components/antigravity/FileInput';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { CountrySelect } from '../../../components/antigravity/CountrySelect';
import type { CompanyProfilePayload } from '../../../types';
import { Breadcrumb } from '../../../components/Breadcrumb';
import { useCompanyProfileForm } from './useCompanyProfileForm';
import type { SectionKey } from './useCompanyProfileForm';
// Country of incorporation is an identity field → full ISO list. The default
// destination is a relocation destination → restricted list (AIQ-1341).
import { COUNTRY_OPTIONS } from '../../policy-config/countryList';
import { DESTINATION_COUNTRIES } from '../../../utils/countries';

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
  /** Eyebrow path shown above the h1. Omit to hide. */
  eyebrow?: string;
  /** Breadcrumb section, e.g. 'HR Operations'. Omit to skip the breadcrumb. */
  breadcrumbSection?: string;
  /** Render the breadcrumb (ReloPass / title) even when no section is set.
   *  Lets a page show "ReloPass / <title>" without an intermediate crumb. */
  showBreadcrumb?: boolean;
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
  breadcrumbSection,
  showBreadcrumb = false,
  title,
  subtitle,
  badge,
  topSlot,
  backTo = '/hr/dashboard',
  backLabel = 'Back to Dashboard',
}: CompanyProfileFormProps) {
  const navigate = useNavigate();

  // ── Section flash (UI animation) ───────────────────────────────────────
  const [sectionFlash, setSectionFlash] = useState<Record<SectionKey, boolean>>({
    identity: false, location: false, hr: false, branding: false,
  });
  const flashTimers = useRef<Record<SectionKey, ReturnType<typeof setTimeout> | null>>({
    identity: null, location: null, hr: null, branding: null,
  });

  useEffect(() => () => {
    Object.values(flashTimers.current).forEach((t) => t && clearTimeout(t));
  }, []);

  const flashSection = useCallback((key: SectionKey) => {
    setSectionFlash((s) => ({ ...s, [key]: true }));
    if (flashTimers.current[key]) clearTimeout(flashTimers.current[key]);
    flashTimers.current[key] = setTimeout(() => {
      setSectionFlash((s) => ({ ...s, [key]: false }));
    }, 2200);
  }, []);

  // ── RHF hook ───────────────────────────────────────────────────────────
  const {
    control,
    register,
    watch,
    saving,
    saveError,
    lastSavedAt,
    isDirty,
    sectionDirty,
    saveNow,
    markSaved,
  } = useCompanyProfileForm(company, onSave, {
    onSaveComplete: (sections) => sections.forEach(flashSection),
  });

  const watchedName = watch('name');

  // ── Logo upload (independent from form save) ───────────────────────────
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const logoUrl = (() => {
    if (!company) return null;
    const v = (company['logo_url'] ?? (company)['logoUrl']) as string | undefined;
    return v ? String(v) : null;
  })();

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
        markSaved();
      } catch (e) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setLogoError(detail ?? 'Upload failed.');
      } finally {
        setLogoUploading(false);
      }
    },
    [onUploadLogo, flashSection, markSaved],
  );

  async function handleRemoveLogo() {
    if (!onRemoveLogo || !logoUrl) return;
    if (!window.confirm('Remove the current logo?')) return;
    setLogoError(null);
    setLogoUploading(true);
    try {
      await onRemoveLogo();
      flashSection('branding');
      markSaved();
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

      {(breadcrumbSection || showBreadcrumb) && (
        <Breadcrumb section={breadcrumbSection} title={title} className="mb-3" />
      )}
      <div className="mb-5">
        {eyebrow && (
          <div className="text-[11px] font-medium uppercase tracking-widest text-slate-500">{eyebrow}</div>
        )}
        <div className="mt-1.5 flex items-baseline gap-3">
          <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">{title}</h1>
          {badge && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent-50 px-2 py-0.5 text-[11px] font-medium text-accent-700 ring-1 ring-inset ring-accent-200">
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
              <Controller
                name="name"
                control={control}
                render={({ field }) => (
                  <Input unstyled
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    className={inputCx}
                    placeholder="e.g. Aurora Energy"
                  />
                )}
              />
            </Field>
            <Field
              label="Legal name"
              helper="Used on official case documents and contracts."
            >
              <Controller
                name="legal_name"
                control={control}
                render={({ field }) => (
                  <Input unstyled
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    className={inputCx}
                    placeholder="e.g. Aurora Energy AS"
                  />
                )}
              />
            </Field>
            <Field label="Industry">
              <select
                {...register('industry')}
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
                {...register('size_band')}
                className={selectCx}
              >
                <option value="">—</option>
                {SIZE_BANDS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Website" full>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[12.5px] text-slate-500">
                  https://
                </span>
                <Controller
                  name="website"
                  control={control}
                  render={({ field }) => (
                    <Input unstyled
                      value={field.value}
                      onChange={(v) => field.onChange(v.replace(/^https?:\/\//, ''))}
                      onBlur={field.onBlur}
                      className={`${inputCx} pl-[60px]`}
                      placeholder="aurora-energy.com"
                    />
                  )}
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
              <Controller
                name="country"
                control={control}
                render={({ field }) => (
                  <CountrySelect
                    value={field.value}
                    onChange={field.onChange}
                    options={COUNTRY_OPTIONS}
                    allowEmpty
                    emptyLabel="—"
                  />
                )}
              />
            </Field>
            <Field label="HQ city">
              <Controller
                name="hq_city"
                control={control}
                render={({ field }) => (
                  <Input unstyled
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    className={inputCx}
                    placeholder="Paris"
                  />
                )}
              />
            </Field>
            <Field label="Address" full>
              <Controller
                name="address"
                control={control}
                render={({ field }) => (
                  <Input unstyled
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    className={inputCx}
                    placeholder="12 Avenue de Friedland, 75008 Paris, France"
                  />
                )}
              />
            </Field>
            <Field
              label="Phone"
              full
              helper="International format with country code."
            >
              <Controller
                name="phone"
                control={control}
                render={({ field }) => (
                  <Input unstyled
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    className={inputCx}
                    placeholder="+33 1 4502 8821"
                  />
                )}
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
              <Controller
                name="hr_contact"
                control={control}
                render={({ field }) => (
                  <Input unstyled
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    className={inputCx}
                    placeholder="helena.muller@aurora-energy.com"
                  />
                )}
              />
            </Field>
            <Field label="Support email">
              <Controller
                name="support_email"
                control={control}
                render={({ field }) => (
                  <Input unstyled
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    className={inputCx}
                    placeholder="mobility@aurora-energy.com"
                  />
                )}
              />
              <InfoBanner>
                <span className="font-medium">Employees see this</span> as their HR contact in the relocation portal.
              </InfoBanner>
            </Field>
            <Field label="Default destination country">
              <Controller
                name="default_destination_country"
                control={control}
                render={({ field }) => (
                  <CountrySelect
                    value={field.value}
                    onChange={field.onChange}
                    options={DESTINATION_COUNTRIES}
                    allowEmpty
                    emptyLabel="—"
                  />
                )}
              />
              <InfoBanner>
                Seeds the destination picker in <span className="font-medium">every new case</span> and drives supplier &amp; resource recommendations.
              </InfoBanner>
            </Field>
            <Field label="Default working location">
              <select
                {...register('default_working_location')}
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
                <span className="text-[11px] text-slate-500">No logo</span>
              )}
            </div>
            <div className="flex-1 space-y-3">
              <div>
                <div className="text-[13.5px] font-semibold text-slate-900">Company logo</div>
                <p className="mt-0.5 text-[12px] text-slate-500">
                  PNG, JPG or SVG · max 2 MB · square 512×512 recommended for best quality.
                </p>
              </div>
              <FileInput
                ref={fileInputRef}
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
                  <Button unstyled
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={logoUploading}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-[12.5px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    <UploadIcon className="h-3.5 w-3.5" />
                    {logoUploading ? 'Uploading…' : logoUrl ? 'Replace' : 'Upload logo'}
                  </Button>
                ) : (
                  <span className="text-[11px] text-slate-500">
                    Logo upload is only available to HR for their own company.
                  </span>
                )}
                {onRemoveLogo && logoUrl && (
                  <Button unstyled
                    type="button"
                    onClick={() => void handleRemoveLogo()}
                    disabled={logoUploading}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-[12.5px] font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                  >
                    <span aria-hidden>×</span> Remove
                  </Button>
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

      {/* Sticky bottom bar */}
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
            <Button unstyled
              type="button"
              onClick={() => navigate(backTo)}
              className="inline-flex items-center gap-1.5 rounded-lg border-2 border-[#0b2b43] bg-white px-4 py-2 text-[13px] font-medium text-[#0b2b43] transition-colors hover:bg-[#e6f2f4] focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-2"
            >
              <span aria-hidden>←</span> {backLabel}
            </Button>
            <Button unstyled
              type="button"
              onClick={() => void saveNow()}
              /* isDirty is already used at the status pill above; the button was the one
                 place that ignored it, so 'Save profile' stayed clickable with nothing
                 to save. */
              disabled={saving || !isDirty || !watchedName.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#0b2b43] px-4 py-2 text-[13px] font-medium text-white shadow-sm transition-colors hover:bg-[#123651] focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <CheckIcon className="h-3.5 w-3.5" /> Save profile
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Visual primitives ──────────────────────────────────────────────────────

const inputCx =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-[13.5px] text-slate-900 placeholder:text-slate-500 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100';

const selectCx =
  'w-full appearance-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-[13.5px] text-slate-900 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100';

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
    <div className="mt-2 inline-flex w-full items-start gap-1.5 rounded-md bg-accent-50/70 px-2.5 py-1.5 text-[11.5px] text-accent-900 ring-1 ring-inset ring-accent-100">
      <InfoIcon className="mt-0.5 h-3 w-3 shrink-0 text-accent-500" />
      <span>{children}</span>
    </div>
  );
}

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
