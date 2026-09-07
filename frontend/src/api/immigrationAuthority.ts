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

export async function getDestinationImmigrationAuthority(
  countryCode: string,
): Promise<DestinationImmigrationAuthority | null> {
  const code = countryCode.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(code)) return null;
  const res = await apiGet<{ authority: DestinationImmigrationAuthority | null }>(
    `/api/employee/immigration-authority/${encodeURIComponent(code)}`,
  );
  const auth = res.authority;
  if (!auth?.url || !auth.url.startsWith('https://')) return null;
  return auth;
}
