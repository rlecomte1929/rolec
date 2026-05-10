import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Card, Alert } from '../components/antigravity';
import { resourcesAPI } from '../api/client';
import { useHrCompanyContext } from '../contexts/HrCompanyContext';
import {
  ResourcesPageContent,
  EMPTY_RESOURCES_FILTERS,
  type ResourcesFilters,
} from '../features/resources/ResourcesPageContent';
import type { ResourcesPagePayload } from '../types';

type FamilyType = 'single' | 'couple' | 'family';
type RelocationType = 'short_term' | 'long_term' | 'permanent';

/**
 * Pilot destinations supported by the platform today. Mirrors the country
 * codes recognised in backend/services/resources/context_service.py
 * (_country_code_from_name) plus the most common European pilot countries
 * HR teams ask about. Edit here when we extend pilot coverage.
 */
const DESTINATION_OPTIONS: ReadonlyArray<{ code: string; name: string }> = [
  { code: 'NO', name: 'Norway' },
  { code: 'SG', name: 'Singapore' },
  { code: 'DE', name: 'Germany' },
  { code: 'UK', name: 'United Kingdom' },
  { code: 'US', name: 'United States' },
  { code: 'FR', name: 'France' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'BE', name: 'Belgium' },
  { code: 'IE', name: 'Ireland' },
  { code: 'ES', name: 'Spain' },
  { code: 'IT', name: 'Italy' },
];

function pickInitialCountry(companyDefault: string | null | undefined): string {
  if (!companyDefault) return 'NO';
  const trimmed = companyDefault.trim();
  if (!trimmed) return 'NO';
  // Try direct code match first (e.g. company stored "DE")
  const byCode = DESTINATION_OPTIONS.find((d) => d.code.toLowerCase() === trimmed.toLowerCase());
  if (byCode) return byCode.code;
  // Then try by name (e.g. "Germany")
  const byName = DESTINATION_OPTIONS.find((d) => d.name.toLowerCase() === trimmed.toLowerCase());
  if (byName) return byName.code;
  return 'NO';
}

export const HrResourcesPreview: React.FC = () => {
  const { company } = useHrCompanyContext();
  const [searchParams, setSearchParams] = useSearchParams();

  const companyDefault = useMemo(() => {
    if (!company) return null;
    const c = company as Record<string, unknown>;
    return (
      (c.default_destination_country as string | undefined) ??
      (c.defaultDestinationCountry as string | undefined) ??
      null
    );
  }, [company]);

  const initialCountry = useMemo(() => pickInitialCountry(companyDefault), [companyDefault]);

  const country = (searchParams.get('country') || initialCountry).toUpperCase();
  const city = searchParams.get('city') || '';
  const familyType = (searchParams.get('family') as FamilyType) || 'single';
  const relocationType = (searchParams.get('reloc') as RelocationType) || 'permanent';

  const updateDestination = useCallback(
    (next: Partial<{ country: string; city: string; family: FamilyType; reloc: RelocationType }>) => {
      const params = new URLSearchParams(searchParams);
      Object.entries(next).forEach(([k, v]) => {
        if (v) params.set(k, String(v));
        else params.delete(k);
      });
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  const filters: ResourcesFilters = useMemo(() => {
    const f: ResourcesFilters = { ...EMPTY_RESOURCES_FILTERS };
    searchParams.forEach((v, k) => {
      if (k in f) (f as Record<string, string>)[k] = v;
    });
    return f;
  }, [searchParams]);

  const updateFilters = useCallback(
    (next: Partial<ResourcesFilters>) => {
      const merged = { ...filters, ...next };
      const params = new URLSearchParams(searchParams);
      Object.entries(merged).forEach(([k, v]) => {
        if (v) params.set(k, v);
        else params.delete(k);
      });
      setSearchParams(params, { replace: true });
    },
    [filters, searchParams, setSearchParams]
  );

  const clearFilters = useCallback(() => {
    // Preserve the destination knobs; only clear content filters.
    const params = new URLSearchParams();
    if (country) params.set('country', country);
    if (city) params.set('city', city);
    if (familyType) params.set('family', familyType);
    if (relocationType) params.set('reloc', relocationType);
    setSearchParams(params, { replace: true });
  }, [country, city, familyType, relocationType, setSearchParams]);

  const [payload, setPayload] = useState<ResourcesPagePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!country) return;
    setLoading(true);
    setError(null);
    const raw = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
    const filterObj: Record<string, string | boolean> = {};
    if (raw.city) filterObj.city = raw.city;
    if (raw.family) filterObj.audienceType = raw.family;
    if (raw.childAge) filterObj.childAge = raw.childAge;
    if (raw.budget) filterObj.budgetTier = raw.budget;
    if (raw.category) filterObj.category = raw.category;
    if (raw.language) filterObj.language = raw.language;
    if (raw.free) filterObj.isFree = raw.free === 'true';
    if (raw.familyFriendly) filterObj.familyFriendly = raw.familyFriendly === 'true';
    if (raw.weekendOnly) filterObj.weekendOnly = raw.weekendOnly === 'true';
    if (raw.eventType) filterObj.eventType = raw.eventType;
    if (raw.search) filterObj.search = raw.search;

    const countryName = DESTINATION_OPTIONS.find((d) => d.code === country)?.name ?? null;
    resourcesAPI
      .getHrPreviewPage(
        {
          countryCode: country,
          countryName,
          city: city || null,
          familyType,
          relocationType,
        },
        Object.keys(filterObj).length ? filterObj : undefined
      )
      .then(setPayload)
      .catch((err: unknown) => {
        const msg =
          (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ||
          (err as Error)?.message ||
          'Unable to load resources preview.';
        setError(String(msg));
        setPayload(null);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [country, city, familyType, relocationType, JSON.stringify(filters)]);

  return (
    <AppShell
      title="Resources preview"
      subtitle="See what an employee in a chosen destination would see on their Resources page."
    >
      <Card padding="md" className="mb-6">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="hr-pv-country" className="block text-xs font-medium text-[#374151] mb-1">
              Destination country
            </label>
            <select
              id="hr-pv-country"
              value={country}
              onChange={(e) => updateDestination({ country: e.target.value })}
              className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
            >
              {DESTINATION_OPTIONS.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name} ({d.code})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="hr-pv-city" className="block text-xs font-medium text-[#374151] mb-1">
              City (optional)
            </label>
            <input
              id="hr-pv-city"
              type="text"
              value={city}
              placeholder="e.g. Oslo"
              onChange={(e) => updateDestination({ city: e.target.value })}
              className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white w-40"
            />
          </div>
          <div>
            <label htmlFor="hr-pv-family" className="block text-xs font-medium text-[#374151] mb-1">
              As employee
            </label>
            <select
              id="hr-pv-family"
              value={familyType}
              onChange={(e) => updateDestination({ family: e.target.value as FamilyType })}
              className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="single">Single</option>
              <option value="couple">Couple</option>
              <option value="family">Family with children</option>
            </select>
          </div>
          <div>
            <label htmlFor="hr-pv-reloc" className="block text-xs font-medium text-[#374151] mb-1">
              Assignment length
            </label>
            <select
              id="hr-pv-reloc"
              value={relocationType}
              onChange={(e) => updateDestination({ reloc: e.target.value as RelocationType })}
              className="border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="short_term">Short term (&lt; 1 yr)</option>
              <option value="long_term">Long term (1–2 yrs)</option>
              <option value="permanent">Permanent</option>
            </select>
          </div>
          <div className="text-xs text-[#6b7280] ml-auto max-w-xs">
            Preview only. No employee receives this. Numbers and personalization update live as you change the
            destination.
          </div>
        </div>
      </Card>

      {error && (
        <Alert variant="error" className="mb-4">
          {error}
        </Alert>
      )}

      {loading && !payload ? (
        <div className="flex flex-col items-center justify-center py-16 text-[#6b7280]">
          <div className="animate-pulse h-8 w-48 bg-[#e2e8f0] rounded mb-4" />
          <div className="animate-pulse h-4 w-64 bg-[#e2e8f0] rounded" />
        </div>
      ) : payload ? (
        <ResourcesPageContent
          payload={payload}
          filters={filters}
          updateFilters={updateFilters}
          clearFilters={clearFilters}
        />
      ) : null}
    </AppShell>
  );
};
