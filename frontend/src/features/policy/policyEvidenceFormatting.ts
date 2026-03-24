/**
 * Human-readable labels for policy assistant evidence metadata (avoid raw API slugs in UI).
 */

const SOURCE_SLUGS: Record<string, string> = {
  published_matrix: 'Policy matrix',
  published_benefit_rule: 'Published benefit rule',
  draft_matrix: 'Draft policy matrix',
  assignment_policy: 'Assignment policy',
  policy_document: 'Policy document',
};

function humanizeSlug(raw: string | null | undefined): string {
  if (!raw?.trim()) return '';
  const key = raw.trim();
  if (SOURCE_SLUGS[key]) return SOURCE_SLUGS[key];
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** One readable attribution line for an evidence row (no duplicate label). */
export function formatEvidenceAttribution(parts: {
  label?: string | null;
  source?: string | null;
  section_ref?: string | null;
  policy_source_type?: string | null;
}): string {
  const label = parts.label?.trim();
  const src = humanizeSlug(parts.source);
  const ptype = humanizeSlug(parts.policy_source_type);
  const section = parts.section_ref?.trim();

  const segments: string[] = [];
  if (label) segments.push(label);
  if (section && !segments.some((s) => s.includes(section))) segments.push(section);

  const extra = [src, ptype].filter(Boolean);
  for (const e of extra) {
    if (!segments.some((s) => s === e || s.includes(e))) segments.push(e);
  }

  return segments.join(' · ') || 'Policy source';
}
