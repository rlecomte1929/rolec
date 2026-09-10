/**
 * Country and city pickers — one place, so no surface invents its own.
 *
 * WHY THIS EXISTS. HR could not reach 29 already-approved Dublin vendors. The
 * `catalog_destination_allowlist` held the destination three ways (`dublin/ireland`,
 * `Dublin/IE`, `Dublin/Ireland`) because the "request a new destination" form took FREE TEXT
 * for city and country. Every mistyped variant became a new dropdown entry, and picking the
 * wrong one returned nothing — so HR requested the destination again, minting another
 * variant. A loop that got worse the more it was used.
 *
 * Free-text city/country inputs are how bad location data gets in. There were 21 of them.
 *
 * TWO DIFFERENT KINDS OF LIST, deliberately:
 *
 *   Country — a CLOSED set. `COUNTRY_OPTIONS` (ISO-3166) is authoritative and nobody should
 *     ever type a country name. `CountryPicker` is a real <select>: you cannot enter a value
 *     that is not on it.
 *
 *   City — an OPEN set. The destination catalogue is deliberately small (AIQ-1656) and a city
 *     not in it must never hard-block someone mid-intake. `CityPicker` suggests from the
 *     catalogue and still accepts a typed value — but it tells the caller, via
 *     `isKnown`, whether what it holds is catalogue-backed, so the caller can route an
 *     unknown city through the admin *request* flow instead of silently writing it.
 *
 * That distinction is the whole point: countries get locked down, cities get curated. Making
 * cities a closed <select> would block a legitimate new destination; leaving countries open
 * is what caused the bug.
 */
import React, { useEffect, useMemo, useState } from 'react';

import { Combobox } from '../Combobox';
import { COUNTRY_OPTIONS } from '../../features/policy-config/countryList';
import { compareCountryDisplayNames, getCountryName } from '../../utils/countries';
import { listEmployeeDestinations, type AllowlistedDestination } from '../../api/destinations';
import { countryFlagEmoji } from '../../lib/countryFlagCode';

function countryOptionLabel(name: string, code?: string): string {
  const display = getCountryName(name) || name;
  const flag = countryFlagEmoji(code || name);
  return flag ? `${flag} ${display}` : display;
}

/** Canonical key for comparing two spellings of one place. Mirrors the backend's
 *  `vendor_curation._canon_city` (lowercase, trimmed, diacritics stripped) so the UI and the
 *  curation read agree on what counts as the same destination — they did not, and that is
 *  half of why the Dublin vendors were unreachable. */
export function canonPlace(value: string | null | undefined): string {
  if (!value) return '';
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

export const COUNTRY_NAMES: string[] = COUNTRY_OPTIONS.map((c) => c.name);

/** Module-level cache: the catalogue is small, static per session, and several pickers can
 *  mount at once. Without this every picker refetches it.
 *
 *  It is deliberately NOT invalidated on a timer. The consequence, stated plainly: a
 *  destination an admin allowlists mid-session does not appear in an already-loaded picker
 *  until the page reloads. That is acceptable for a catalogue that changes a few times a
 *  week, and `resetDestinationCatalog()` is the seam to call if that stops being true. */
let _cache: AllowlistedDestination[] | null = null;
let _inflight: Promise<AllowlistedDestination[]> | null = null;

/** Drop the cached catalogue so the next mount refetches. Used by tests, and the hook to
 *  call after an admin adds a destination. */
export function resetDestinationCatalog(): void {
  _cache = null;
  _inflight = null;
}

export function useDestinationCatalog(): {
  destinations: AllowlistedDestination[];
  countryNames: string[];
  citiesForCountry: (country: string) => string[];
  loading: boolean;
} {
  const [destinations, setDestinations] = useState<AllowlistedDestination[]>(_cache ?? []);
  const [loading, setLoading] = useState(_cache === null);

  useEffect(() => {
    if (_cache !== null) return;
    let cancelled = false;
    _inflight = _inflight ?? listEmployeeDestinations();
    _inflight
      .then((d) => {
        _cache = d;
        if (!cancelled) { setDestinations(d); setLoading(false); }
      })
      // Fail-soft: a catalogue that will not load must not disable the form. The country
      // list is local, so countries keep working; cities fall back to free entry.
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const citiesForCountry = useMemo(
    () => (country: string): string[] => {
      const want = canonPlace(country);
      if (!want) return [];
      const seen = new Set<string>();
      const out: string[] = [];
      // Match on the canonical key, so a catalogue row spelled 'ireland' still answers a
      // pick of 'Ireland'. De-duped for the same reason.
      for (const d of destinations) {
        if (canonPlace(d.country) !== want) continue;
        const key = canonPlace(d.city);
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(d.city);
      }
      return out.sort((a, b) => a.localeCompare(b, 'en'));
    },
    [destinations],
  );

  return { destinations, countryNames: COUNTRY_NAMES, citiesForCountry, loading };
}

// ── Country: a closed list. No typing. ────────────────────────────────────────────────

export const CountryPicker: React.FC<{
  value: string;
  onChange: (v: string) => void;
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  testId?: string;
  className?: string;
  /** Restrict the list (e.g. to the destinations a catalogue actually covers). */
  options?: string[];
  /**
   * What the picker STORES. Several admin filters key on an ISO `country_code`, so handing
   * them a country name would send a value their query can never match — a dropdown that
   * silently returns nothing is no better than the free-text box it replaced.
   */
  valueMode?: 'name' | 'code';
}> = ({ value, onChange, label, placeholder = 'Select a country…', disabled, testId, className, options, valueMode = 'name' }) => {
  if (valueMode === 'code' && !options) {
    return (
      <label className={`block ${className ?? ''}`}>
        {label && <span className="block text-sm font-medium text-[#0b2b43] mb-1">{label}</span>}
        <select
          aria-label={label || 'Country'}
          data-testid={testId}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43] disabled:bg-[#f1f5f9] disabled:text-slate-500"
        >
          <option value="">{placeholder}</option>
          {COUNTRY_OPTIONS.map((c) => (
            <option key={c.code} value={c.code}>{countryOptionLabel(c.name, c.code)}</option>
          ))}
        </select>
      </label>
    );
  }
  const list = [...(options ?? COUNTRY_NAMES)].sort(compareCountryDisplayNames);
  // A stored value that is not on the list (legacy free-text data) is offered as its own
  // option rather than silently blanked — losing what someone previously saved would be a
  // worse bug than the one this fixes. Sorted with the rest so a stray ISO code does not
  // jump to the top of an otherwise A–Z list.
  const extra = value && !list.some((o) => canonPlace(o) === canonPlace(value));
  const withCurrent = extra ? [value, ...list].sort(compareCountryDisplayNames) : list;
  return (
    <label className={`block ${className ?? ''}`}>
      {label && <span className="block text-sm font-medium text-[#0b2b43] mb-1">{label}</span>}
      <select
        aria-label={label || 'Country'}
        data-testid={testId}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43] disabled:bg-[#f1f5f9] disabled:text-slate-500"
      >
        <option value="">{placeholder}</option>
        {withCurrent.map((c) => (
          <option key={c} value={c}>{countryOptionLabel(c)}</option>
        ))}
      </select>
    </label>
  );
};

// ── City: catalogue-backed suggestions, typed values still allowed. ───────────────────

export const CityPicker: React.FC<{
  value: string;
  onChange: (v: string) => void;
  /** Country name — scopes the suggestions. */
  country?: string;
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  testId?: string;
  /** Told whether the current value is catalogue-backed, so the caller can route an unknown
   *  city through the destination-request flow rather than writing it blind. */
  onKnownChange?: (isKnown: boolean) => void;
}> = ({ value, onChange, country, label, placeholder, disabled, testId, onKnownChange }) => {
  const { citiesForCountry, loading } = useDestinationCatalog();
  const { destinations } = useDestinationCatalog();
  const options = useMemo(() => {
    // country prop absent  -> unscoped: every catalogue city (search/filter use)
    // country prop present -> scoped, and empty means "pick a country first" (data entry)
    if (country === undefined) {
      const seen = new Set<string>();
      const all: string[] = [];
      for (const d of destinations) {
        const key = canonPlace(d.city);
        if (!key || seen.has(key)) continue;
        seen.add(key);
        all.push(d.city);
      }
      return all.sort((a, b) => a.localeCompare(b, 'en'));
    }
    return country ? citiesForCountry(country) : [];
  }, [country, citiesForCountry, destinations]);
  const isKnown = useMemo(
    () => options.some((o) => canonPlace(o) === canonPlace(value)),
    [options, value],
  );
  useEffect(() => { onKnownChange?.(isKnown); }, [isKnown, onKnownChange]);

  return (
    <Combobox
      label={label}
      value={value}
      onChange={onChange}
      options={options}
      disabled={disabled || loading}
      testId={testId}
      placeholder={
        placeholder
        ?? (country === undefined || country ? 'Select or type a city…' : 'Select a country first')
      }
    />
  );
};
