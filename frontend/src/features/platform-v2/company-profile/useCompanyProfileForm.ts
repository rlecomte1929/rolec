import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import type { CompanyProfilePayload } from '../../../types';

// ── Form schema ──────────────────────────────────────────────────────────────

export type CompanyProfileFormValues = {
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

export type SectionKey = 'identity' | 'location' | 'hr' | 'branding';

const SECTION_FIELDS: Record<SectionKey, (keyof CompanyProfileFormValues)[]> = {
  identity: ['name', 'legal_name', 'industry', 'size_band', 'website'],
  location: ['country', 'hq_city', 'address', 'phone'],
  hr: ['hr_contact', 'support_email', 'default_destination_country', 'default_working_location'],
  branding: [],
};

/** Host-only website: strip protocol and surrounding space for the https:// overlay. */
export function sanitizeWebsiteHost(value: string): string {
  return value.trim().replace(/^https?:\/\//i, '').trim();
}

export function emptyValues(): CompanyProfileFormValues {
  return {
    name: '', legal_name: '', industry: '', size_band: '', website: '',
    country: '', hq_city: '', address: '', phone: '',
    hr_contact: '', support_email: '',
    default_destination_country: '', default_working_location: '',
  };
}

/** Adapt a raw company record (snake or camel keys) → form values. */
export function valuesFromCompany(company: Record<string, unknown> | null): CompanyProfileFormValues {
  if (!company) return emptyValues();
  const pick = (snake: string, camel: string) => {
    const v = company[snake] ?? company[camel];
    return typeof v === 'string' ? v.trim() : typeof v === 'number' ? String(v) : '';
  };
  return {
    name:                        pick('name', 'name'),
    legal_name:                  pick('legal_name', 'legalName'),
    industry:                    pick('industry', 'industry'),
    size_band:                   pick('size_band', 'sizeBand'),
    website:                     sanitizeWebsiteHost(pick('website', 'website')),
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

/** Adapt form values → API payload (drops empty-string optionals). */
export function valuesToPayload(values: CompanyProfileFormValues): CompanyProfilePayload {
  const opt = (v: string): string | undefined => v.trim() || undefined;
  return {
    name: values.name.trim(),
    legal_name:                  opt(values.legal_name),
    industry:                    opt(values.industry),
    size_band:                   opt(values.size_band),
    website:                     opt(sanitizeWebsiteHost(values.website)),
    country:                     opt(values.country),
    hq_city:                     opt(values.hq_city),
    address:                     opt(values.address),
    phone:                       opt(values.phone),
    hr_contact:                  opt(values.hr_contact),
    support_email:               opt(values.support_email),
    default_destination_country: opt(values.default_destination_country),
    default_working_location:    opt(values.default_working_location),
  };
}

// ── Hook ─────────────────────────────────────────────────────────────────────

const AUTOSAVE_DEBOUNCE_MS = 1500;

export interface UseCompanyProfileFormOptions {
  onSaveComplete?: (sections: SectionKey[]) => void;
}

export function useCompanyProfileForm(
  company: Record<string, unknown> | null,
  onSave: (payload: CompanyProfilePayload) => Promise<void>,
  options?: UseCompanyProfileFormOptions,
) {
  const methods = useForm<CompanyProfileFormValues>({
    defaultValues: valuesFromCompany(company),
    mode: 'onChange',
  });

  const { reset, watch, formState, getValues } = methods;

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSaveRef = useRef(onSave);
  onSaveRef.current = onSave;
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    reset(valuesFromCompany(company));
  }, [company, reset]);

  const sectionDirty = useMemo<Record<SectionKey, boolean>>(() => {
    const df = formState.dirtyFields;
    return {
      identity: !!(df.name || df.legal_name || df.industry || df.size_band || df.website),
      location: !!(df.country || df.hq_city || df.address || df.phone),
      hr: !!(df.hr_contact || df.support_email || df.default_destination_country || df.default_working_location),
      branding: false,
    };
  }, [formState.dirtyFields]);

  const persist = useCallback(
    async (values: CompanyProfileFormValues, sections: SectionKey[]) => {
      if (!values.name.trim()) {
        setSaveError('Company name is required.');
        return;
      }
      setSaveError(null);
      setSaving(true);
      try {
        await onSaveRef.current(valuesToPayload(values));
        reset(values, { keepValues: true });
        setLastSavedAt(Date.now());
        optionsRef.current?.onSaveComplete?.(sections);
      } catch (e) {
        const err = e as { response?: { status?: number; data?: { detail?: string } }; message?: string };
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail;
        if (detail) setSaveError(detail);
        else if (status === 500) setSaveError('Server error — check the uvicorn terminal for the Python traceback.');
        else if (status === 403) setSaveError('Permission denied — your session may have expired.');
        else if (status === 422) setSaveError('The form data was rejected by the server (validation error).');
        else setSaveError(err?.message ?? 'Failed to save profile.');
      } finally {
        setSaving(false);
      }
    },
    [reset],
  );

  // Debounced autosave
  useEffect(() => {
    const sub = watch(() => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const currentValues = getValues();
        const df = formState.dirtyFields;
        const dirty = Object.keys(df).length > 0;
        if (!dirty) return;
        const sections = (Object.keys(SECTION_FIELDS) as SectionKey[]).filter((s) =>
          SECTION_FIELDS[s].some((f) => df[f]),
        );
        void persist(currentValues, sections);
      }, AUTOSAVE_DEBOUNCE_MS);
    });
    return () => {
      sub.unsubscribe();
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [watch, getValues, formState.dirtyFields, persist]);

  const saveNow = useCallback(async () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const currentValues = getValues();
    const df = formState.dirtyFields;
    // Nothing dirty means the debounced autosave already persisted everything, so this
    // would POST (and then GET, via handleSave's refresh) purely to rewrite what is
    // already stored. The old `: ['identity','location','hr']` fallback WAS that path —
    // an explicit "save everything anyway" for a form with no pending edits.
    if (Object.keys(df).length === 0) return;
    const sections = (Object.keys(SECTION_FIELDS) as SectionKey[]).filter((s) =>
      SECTION_FIELDS[s].some((f) => df[f]),
    );
    if (sections.length === 0) return;
    await persist(currentValues, sections);
  }, [getValues, formState.dirtyFields, persist]);

  const markSaved = useCallback(() => {
    setLastSavedAt(Date.now());
  }, []);

  const clearError = useCallback(() => {
    setSaveError(null);
  }, []);

  return {
    ...methods,
    saving,
    saveError,
    lastSavedAt,
    isDirty: formState.isDirty,
    sectionDirty,
    saveNow,
    markSaved,
    clearError,
  };
}
