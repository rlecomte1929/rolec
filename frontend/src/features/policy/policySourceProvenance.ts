/**
 * Display helpers for policy Layer-2 source provenance (section refs are not benefit values).
 */

export type PolicySourceProvenanceV1 = {
  schema?: string;
  document_id?: string | null;
  page?: number | null;
  page_end?: number | null;
  section_ref?: string | null;
  source_label?: string | null;
  source_excerpt?: string | null;
  clause_id?: string | null;
};

export function getSourceProvenance(meta: unknown): PolicySourceProvenanceV1 | null {
  if (!meta || typeof meta !== 'object') return null;
  const m = meta as Record<string, unknown>;
  const sp = m.source_provenance;
  if (!sp || typeof sp !== 'object') return null;
  return sp as PolicySourceProvenanceV1;
}

/** e.g. "Source: section 2.1" for HR review tables */
export function formatPolicySourceCitation(sp: PolicySourceProvenanceV1 | null): string {
  if (!sp?.section_ref) return '';
  return `Source: section ${String(sp.section_ref).trim()}`;
}
