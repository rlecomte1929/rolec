/**
 * Pure helpers for the HR vendor-curation service-type filter.
 *
 * Service-type tags are free-form (assigned by the AI populate path) and live in
 * each row's `attributes.service_types`. These helpers extract them, build the
 * filter dropdown options (case-insensitive union, first-seen casing wins), and
 * filter rows by a selected type. Kept pure + framework-free so they're unit-testable
 * without rendering the page.
 */

export interface HasAttributes {
  attributes?: Record<string, unknown>;
}

/** The non-empty, string service-type tags on a row (defensive about shape). */
export function rowServiceTypes(row: HasAttributes): string[] {
  const raw = row.attributes?.service_types;
  if (!Array.isArray(raw)) return [];
  return raw.map((x) => String(x)).filter((s) => s.trim().length > 0);
}

/**
 * Sorted, case-insensitively de-duplicated union of service types across rows.
 * The first-seen casing is preserved as the display label (e.g. "International"
 * wins over a later "international").
 */
export function serviceTypeOptions(rows: HasAttributes[]): string[] {
  const seen = new Map<string, string>(); // lowercased key -> display label
  for (const r of rows) {
    for (const t of rowServiceTypes(r)) {
      const key = t.toLowerCase();
      if (!seen.has(key)) seen.set(key, t);
    }
  }
  return Array.from(seen.values()).sort((a, b) => a.localeCompare(b));
}

/**
 * Filter rows by a selected service type (case-insensitive). An empty/falsey
 * filter returns every row unchanged ("All").
 */
export function filterByServiceType<T extends HasAttributes>(rows: T[], filter: string): T[] {
  if (!filter) return rows;
  const want = filter.toLowerCase();
  return rows.filter((r) => rowServiceTypes(r).some((t) => t.toLowerCase() === want));
}
