import { countryFlagCode } from '../lib/countryFlagCode';
import { apiGet } from './client';

/**
 * Standing destination immigration-authority link (IDR-260820-28EC).
 * GET /api/employee/immigration-authority/{countryCode}
 * `authority` is null when nothing curated exists — the UI must render nothing.
 */
export interface DestinationImmigrationAuthority {
  name: string;
  url: string;
  source?: string;
}

/** CountryPicker stores names ("Germany"); the API keys on ISO-2 ("DE"). */
export function toDestinationIso2(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (/^[A-Za-z]{2}$/.test(trimmed)) return trimmed.toUpperCase();
  const mapped = countryFlagCode(trimmed);
  return mapped ? mapped.toUpperCase() : null;
}

export async function getDestinationImmigrationAuthority(
  countryCode: string,
): Promise<DestinationImmigrationAuthority | null> {
  const code = toDestinationIso2(countryCode);
  if (!code) return null;
  const res = await apiGet<{ authority: DestinationImmigrationAuthority | null }>(
    `/api/employee/immigration-authority/${encodeURIComponent(code)}`,
  );
  const auth = res.authority;
  if (!auth?.url || !auth.url.startsWith('https://')) return null;
  return auth;
}
