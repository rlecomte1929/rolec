import type { AdminRequirementReview, ReviewStatus } from '../../api/admin';
import { countryName } from '../../features/policy-config/countryList';
import { countryFlagCode } from '../../lib/countryFlagCode';
import type { CountryListDTO } from '../../types';

export type CountryListRow = CountryListDTO['countries'][number];
export type CatalogSortKey = 'name' | 'requirements' | 'confidence' | 'updated';
export type CatalogAttention = 'all' | 'empty' | 'refresh';
export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'unknown';

/** Catalog rows older than this are flagged so admins can find stale coverage. */
export const CATALOG_STALE_DAYS = 90;

export function displayCountryName(code: string): string {
  const iso = countryFlagCode(code);
  if (iso) return countryName(iso.toUpperCase());
  return countryName(code);
}

export function displayCountryIso(code: string): string | null {
  const iso = countryFlagCode(code);
  return iso ? iso.toUpperCase() : null;
}

export function confidencePercent(score: number | undefined | null): number | null {
  if (score === undefined || score === null || Number.isNaN(score)) return null;
  if (score < 0) return 0;
  if (score <= 1) return Math.round(score * 100);
  return Math.round(Math.min(score, 100));
}

export function confidenceLevel(score: number | undefined | null): ConfidenceLevel {
  const pct = confidencePercent(score);
  if (pct === null) return 'unknown';
  if (pct >= 75) return 'high';
  if (pct >= 40) return 'medium';
  return 'low';
}

/** Stored research scores are not catalog quality. Empty rows must not read as High. */
export function catalogConfidenceScore(
  row: Pick<CountryListRow, 'confidenceScore' | 'requirementsCount' | 'topDomains'>,
): number | null {
  const requirements = row.requirementsCount || 0;
  const sources = (row.topDomains || []).length;
  if (requirements <= 0) return null;
  if (sources <= 0) {
    const pct = confidencePercent(row.confidenceScore);
    if (pct === null) return null;
    return Math.min(row.confidenceScore ?? 0, 0.39);
  }
  return row.confidenceScore ?? null;
}

export function isCatalogStale(
  lastUpdatedAt: string | undefined,
  now: Date = new Date(),
): boolean {
  if (!lastUpdatedAt) return true;
  const then = new Date(lastUpdatedAt);
  if (Number.isNaN(then.getTime())) return true;
  const ageMs = now.getTime() - then.getTime();
  return ageMs >= CATALOG_STALE_DAYS * 24 * 60 * 60 * 1000;
}

export function formatUpdatedLabel(
  lastUpdatedAt: string | undefined,
  now: Date = new Date(),
): { absolute: string; relative: string } {
  if (!lastUpdatedAt) {
    return { absolute: 'Never', relative: 'Never updated' };
  }
  const then = new Date(lastUpdatedAt);
  if (Number.isNaN(then.getTime())) {
    return { absolute: 'Unknown', relative: 'Unknown date' };
  }
  const absolute = then.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
  const dayMs = 24 * 60 * 60 * 1000;
  const startNow = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const startThen = Date.UTC(then.getUTCFullYear(), then.getUTCMonth(), then.getUTCDate());
  const days = Math.floor((startNow - startThen) / dayMs);
  if (days < 0) return { absolute, relative: absolute };
  if (days === 0) return { absolute, relative: 'Today' };
  if (days === 1) return { absolute, relative: 'Yesterday' };
  if (days < 30) return { absolute, relative: `${days} days ago` };
  const months = Math.floor(days / 30);
  if (days < 365) {
    return { absolute, relative: months === 1 ? '1 month ago' : `${months} months ago` };
  }
  const years = Math.floor(days / 365);
  return { absolute, relative: years === 1 ? '1 year ago' : `${years} years ago` };
}

export function summarizeCatalog(rows: CountryListRow[], now: Date = new Date()) {
  return {
    countries: rows.length,
    requirements: rows.reduce((sum, row) => sum + (row.requirementsCount || 0), 0),
    empty: rows.filter((row) => (row.requirementsCount || 0) === 0).length,
    needsRefresh: rows.filter((row) => isCatalogStale(row.lastUpdatedAt, now)).length,
  };
}

export function filterCatalog(
  rows: CountryListRow[],
  query: string,
  attention: CatalogAttention,
  now: Date = new Date(),
): CountryListRow[] {
  const q = query.trim().toLowerCase();
  return rows.filter((row) => {
    if (attention === 'empty' && (row.requirementsCount || 0) !== 0) return false;
    if (attention === 'refresh' && !isCatalogStale(row.lastUpdatedAt, now)) return false;
    if (!q) return true;
    const name = displayCountryName(row.countryCode).toLowerCase();
    const code = row.countryCode.toLowerCase();
    const domains = row.topDomains.join(' ').toLowerCase();
    return name.includes(q) || code.includes(q) || domains.includes(q);
  });
}

export type RequirementStatusFilter = 'all' | ReviewStatus;

const REVIEW_SORT: Record<ReviewStatus, number> = {
  pending: 0,
  approved: 1,
  rejected: 2,
};

export function displayCatalogLabel(value: string | undefined | null): string {
  const raw = (value || '').trim();
  if (!raw) return 'Uncategorised';
  return raw
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function countRequirementStatuses(items: AdminRequirementReview[]) {
  return {
    all: items.length,
    pending: items.filter((item) => item.reviewStatus === 'pending').length,
    approved: items.filter((item) => item.reviewStatus === 'approved').length,
    rejected: items.filter((item) => item.reviewStatus === 'rejected').length,
  };
}

export function filterRequirements(
  items: AdminRequirementReview[],
  query: string,
  status: RequirementStatusFilter,
): AdminRequirementReview[] {
  const q = query.trim().toLowerCase();
  return items.filter((item) => {
    if (status !== 'all' && item.reviewStatus !== status) return false;
    if (!q) return true;
    const hay = [
      item.title,
      item.description,
      item.pillar,
      item.purpose,
      item.owner,
      item.severity,
      ...item.citations.map((citation) => citation.title),
    ]
      .join(' ')
      .toLowerCase();
    return hay.includes(q);
  });
}

export function groupRequirementsByPillar(
  items: AdminRequirementReview[],
): { pillar: string; items: AdminRequirementReview[] }[] {
  const sorted = [...items].sort((a, b) => {
    const byStatus = REVIEW_SORT[a.reviewStatus] - REVIEW_SORT[b.reviewStatus];
    if (byStatus !== 0) return byStatus;
    return a.title.localeCompare(b.title, 'en');
  });
  const groups = new Map<string, AdminRequirementReview[]>();
  for (const item of sorted) {
    const pillar = item.pillar || 'Uncategorised';
    const list = groups.get(pillar) ?? [];
    list.push(item);
    groups.set(pillar, list);
  }
  return [...groups.entries()].map(([pillar, grouped]) => ({ pillar, items: grouped }));
}

export function sortCatalog(rows: CountryListRow[], sort: CatalogSortKey): CountryListRow[] {
  const copy = [...rows];
  copy.sort((a, b) => {
    if (sort === 'requirements') return (b.requirementsCount || 0) - (a.requirementsCount || 0);
    if (sort === 'confidence') {
      const av = catalogConfidenceScore(a) ?? -1;
      const bv = catalogConfidenceScore(b) ?? -1;
      return bv - av;
    }
    if (sort === 'updated') {
      const at = a.lastUpdatedAt ? new Date(a.lastUpdatedAt).getTime() : 0;
      const bt = b.lastUpdatedAt ? new Date(b.lastUpdatedAt).getTime() : 0;
      return bt - at;
    }
    return displayCountryName(a.countryCode).localeCompare(displayCountryName(b.countryCode), 'en');
  });
  return copy;
}
