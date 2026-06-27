/**
 * RHF wrapper for the company profile form (AIQ-1201).
 *
 * Migration target for CompanyProfileForm.tsx — this hook encapsulates the
 * react-hook-form setup so the component can be migrated field by field.
 * The existing component continues to use useState-based form state until the
 * migration PR lands; this file establishes the schema and autosave pattern.
 *
 * Usage (future):
 *   const { register, handleSubmit, watch, formState, reset } = useCompanyProfileForm(company);
 *   <Input {...register('name')} />
 */
import { useCallback, useEffect } from 'react';
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

/** Adapt form values → API payload (drops empty-string optionals). */
export function valuesToPayload(values: CompanyProfileFormValues): CompanyProfilePayload {
  const opt = (v: string): string | undefined => v.trim() || undefined;
  return {
    name: values.name.trim(),
    legal_name:                  opt(values.legal_name),
    industry:                    opt(values.industry),
    size_band:                   opt(values.size_band),
    website:                     opt(values.website),
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

export function useCompanyProfileForm(
  company: Record<string, unknown> | null,
  onSave: (payload: CompanyProfilePayload) => Promise<void>,
) {
  const methods = useForm<CompanyProfileFormValues>({
    defaultValues: valuesFromCompany(company),
    mode: 'onChange',
  });

  const { reset, watch, handleSubmit } = methods;

  // Re-seed the form whenever the source data changes (e.g. after a fresh fetch).
  useEffect(() => {
    reset(valuesFromCompany(company));
  }, [company, reset]);

  // Debounced autosave: watch all fields and trigger onSave after AUTOSAVE_DEBOUNCE_MS
  // of silence. Mirrors the existing autosave pattern in CompanyProfileForm.tsx.
  const submitValues = useCallback(
    async (values: CompanyProfileFormValues) => {
      await onSave(valuesToPayload(values));
    },
    [onSave],
  );

  useEffect(() => {
    const sub = watch(() => {
      const tid = window.setTimeout(() => {
        void handleSubmit(submitValues)();
      }, AUTOSAVE_DEBOUNCE_MS);
      return () => window.clearTimeout(tid);
    });
    return () => sub.unsubscribe();
  }, [watch, handleSubmit, submitValues]);

  return methods;
}
