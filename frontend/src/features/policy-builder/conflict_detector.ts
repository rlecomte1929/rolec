/**
 * [P2-5] conflict_detector.ts
 *
 * Deterministic conflict detection engine for extracted policy values.
 * No LLM calls — pure TypeScript with numeric tolerance and string normalisation.
 *
 * Detects three types of contradictions:
 *   1. Intra-document  — same policy document defines a benefit differently in two sections
 *   2. Inter-document  — two uploaded documents disagree on same category+tier
 *   3. Version conflict — new upload contradicts the currently published active policy
 *
 * Rules:
 *   - Numeric values: consistent within ±2% tolerance
 *   - String values:  compared after normalising to lowercase + collapsed whitespace
 *   - High severity   = monetary (numeric) contradiction
 *   - Medium severity = condition-only contradiction (same value, different conditions)
 *
 * Conflicts stored in policy_conflicts table pending HR resolution.
 * A category CANNOT be published if it has unresolved high-severity conflicts.
 */

import { isConsistentWithExisting } from './confidence_scorer';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A single extracted policy value — the input unit for conflict detection */
export interface PolicyFactInput {
  /** Unique identifier — used to avoid self-comparison */
  id: string;
  /** Category code, e.g. 'CAT-01' */
  category_code: string;
  /** Tier/grade label, e.g. 'Manager'; null = applies to all tiers */
  tier: string | null;
  /** Extracted numeric or string value */
  normalized_value: {
    value?: string | number | null;
    currency?: string | null;
    unit?: string | null;
    condition?: string | null;
  };
  /** Source document filename or identifier */
  source_doc: string;
  /** Source page number within the document */
  source_page?: number | null;
  /** Snapshot ID — used to identify which document version this came from */
  snapshot_id?: string | null;
}

export interface ConflictValue {
  value: string | number | null;
  currency?: string | null;
  unit?: string | null;
  source_doc: string;
  page?: number | null;
}

export type ConflictType = 'intra_document' | 'inter_document' | 'version_conflict';
export type ConflictSeverity = 'high' | 'medium';

export interface ConflictReport {
  /** UUID for this conflict — caller should persist with gen_random_uuid() equivalent */
  conflict_id: string;
  /** Conflict type */
  conflict_type: ConflictType;
  /** Category the conflict belongs to */
  category_code: string;
  /** Tier the conflict belongs to (null = all-tier conflict) */
  tier: string | null;
  /** First conflicting value */
  value_a: ConflictValue;
  /** Second conflicting value */
  value_b: ConflictValue;
  /**
   * high   = monetary/numeric contradiction (blocks publication)
   * medium = condition-only contradiction (flagged but does not block)
   */
  severity: ConflictSeverity;
  /** ISO timestamp when conflict was detected */
  detected_at: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Simple deterministic UUID v4 substitute for pure-TS environments */
function newConflictId(): string {
  // Use crypto.randomUUID() where available, else fallback to timestamp+random
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  const ts = Date.now().toString(16);
  const rand = Math.floor(Math.random() * 0xffffffffffff).toString(16).padStart(12, '0');
  return `${ts.slice(0, 8)}-${ts.slice(8, 12)}-4${rand.slice(0, 3)}-8${rand.slice(3, 6)}-${rand.slice(6)}`;
}

function normaliseKey(categoryCode: string, tier: string | null): string {
  return `${categoryCode.toLowerCase()}::${(tier ?? '').toLowerCase().trim()}`;
}

function toConflictValue(fact: PolicyFactInput): ConflictValue {
  return {
    value: fact.normalized_value.value ?? null,
    currency: fact.normalized_value.currency ?? null,
    unit: fact.normalized_value.unit ?? null,
    source_doc: fact.source_doc,
    page: fact.source_page ?? null,
  };
}

/**
 * Determine whether two facts actually conflict.
 *
 * Returns the severity level if they conflict, or null if they are consistent.
 *   - If numeric values differ beyond ±2% → 'high'
 *   - If values are the same but conditions differ → 'medium'
 *   - Otherwise → null (no conflict)
 */
function detectConflict(
  a: PolicyFactInput,
  b: PolicyFactInput,
): ConflictSeverity | null {
  const aVal = a.normalized_value.value;
  const bVal = b.normalized_value.value;

  // Both null — no conflict
  if (aVal == null && bVal == null) return null;

  // One null, one set — treat as high severity (one doc says "nothing", another says a value)
  if (aVal == null || bVal == null) return 'high';

  // Numeric comparison
  const aNum = parseFloat(String(aVal).replace(/[,\s]/g, '').replace(/[^0-9.]/g, ''));
  const bNum = parseFloat(String(bVal).replace(/[,\s]/g, '').replace(/[^0-9.]/g, ''));

  if (!Number.isNaN(aNum) && !Number.isNaN(bNum)) {
    const consistent = isConsistentWithExisting(aVal, { value: bNum });
    if (!consistent) return 'high';

    // Values are numerically consistent — check conditions for medium severity
    const aCond = (a.normalized_value.condition ?? '').toLowerCase().trim();
    const bCond = (b.normalized_value.condition ?? '').toLowerCase().trim();
    if (aCond !== bCond && (aCond.length > 0 || bCond.length > 0)) return 'medium';

    return null;
  }

  // String comparison (normalised)
  const normalise = (v: string | number) =>
    String(v).toLowerCase().replace(/\s+/g, ' ').trim();
  if (normalise(aVal) !== normalise(bVal)) return 'high';

  // Same string value — check conditions
  const aCond = (a.normalized_value.condition ?? '').toLowerCase().trim();
  const bCond = (b.normalized_value.condition ?? '').toLowerCase().trim();
  if (aCond !== bCond && (aCond.length > 0 || bCond.length > 0)) return 'medium';

  return null;
}

// ---------------------------------------------------------------------------
// Main detector functions
// ---------------------------------------------------------------------------

/**
 * Detect intra-document conflicts within a single set of facts from one document.
 *
 * A conflict occurs when two facts share the same (category_code, tier) but carry
 * different values — e.g. Section 3 says EUR 3,000 while Section 7 says EUR 3,500.
 */
export function detectIntraDocConflicts(facts: PolicyFactInput[]): ConflictReport[] {
  const reports: ConflictReport[] = [];
  const now = new Date().toISOString();

  // Group by normalised (category, tier) key
  const groups = new Map<string, PolicyFactInput[]>();
  for (const fact of facts) {
    const key = normaliseKey(fact.category_code, fact.tier);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(fact);
  }

  for (const [, group] of groups) {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        const a = group[i];
        const b = group[j];
        if (!a || !b) continue;
        if (a.id === b.id) continue;

        const severity = detectConflict(a, b);
        if (severity == null) continue;

        reports.push({
          conflict_id: newConflictId(),
          conflict_type: 'intra_document',
          category_code: a.category_code,
          tier: a.tier,
          value_a: toConflictValue(a),
          value_b: toConflictValue(b),
          severity,
          detected_at: now,
        });
      }
    }
  }

  return reports;
}

/**
 * Detect inter-document conflicts between facts from two or more documents.
 *
 * Each fact must carry a distinct source_doc. Only pairs from different documents
 * are compared (intra-doc pairs are handled by detectIntraDocConflicts).
 */
export function detectInterDocConflicts(facts: PolicyFactInput[]): ConflictReport[] {
  const reports: ConflictReport[] = [];
  const now = new Date().toISOString();

  // Group by normalised (category, tier) key
  const groups = new Map<string, PolicyFactInput[]>();
  for (const fact of facts) {
    const key = normaliseKey(fact.category_code, fact.tier);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(fact);
  }

  // Track already-reported pairs to avoid duplicates
  const reported = new Set<string>();

  for (const [, group] of groups) {
    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        const a = group[i];
        const b = group[j];
        if (!a || !b) continue;
        if (a.id === b.id) continue;
        if (a.source_doc === b.source_doc) continue; // intra-doc — skip

        const pairKey = [a.id, b.id].sort().join('::');
        if (reported.has(pairKey)) continue;

        const severity = detectConflict(a, b);
        if (severity == null) continue;

        reported.add(pairKey);
        reports.push({
          conflict_id: newConflictId(),
          conflict_type: 'inter_document',
          category_code: a.category_code,
          tier: a.tier,
          value_a: toConflictValue(a),
          value_b: toConflictValue(b),
          severity,
          detected_at: now,
        });
      }
    }
  }

  return reports;
}

/**
 * Detect version conflicts — new facts contradicting the currently published policy.
 *
 * @param newFacts      Facts extracted from the newly uploaded document
 * @param publishedFacts Facts from the currently active/published policy snapshot
 */
export function detectVersionConflicts(
  newFacts: PolicyFactInput[],
  publishedFacts: PolicyFactInput[],
): ConflictReport[] {
  const reports: ConflictReport[] = [];
  const now = new Date().toISOString();

  // Index published facts by (category, tier) → first match
  const publishedIndex = new Map<string, PolicyFactInput>();
  for (const fact of publishedFacts) {
    const key = normaliseKey(fact.category_code, fact.tier);
    if (!publishedIndex.has(key)) publishedIndex.set(key, fact);
  }

  for (const newFact of newFacts) {
    const key = normaliseKey(newFact.category_code, newFact.tier);
    const published = publishedIndex.get(key);
    if (!published) continue;

    const severity = detectConflict(newFact, published);
    if (severity == null) continue;

    reports.push({
      conflict_id: newConflictId(),
      conflict_type: 'version_conflict',
      category_code: newFact.category_code,
      tier: newFact.tier,
      value_a: toConflictValue(newFact),
      value_b: toConflictValue(published),
      severity,
      detected_at: now,
    });
  }

  return reports;
}

/**
 * Run all three conflict detection passes and return a combined de-duplicated list.
 *
 * Pass all facts from the new upload as `newFacts`.
 * Pass facts from all *other* documents (same company) as `existingFacts`.
 * Pass facts from the published policy as `publishedFacts` (may overlap with existingFacts).
 */
export function detectAllConflicts(opts: {
  newFacts: PolicyFactInput[];
  existingFacts?: PolicyFactInput[];
  publishedFacts?: PolicyFactInput[];
}): ConflictReport[] {
  const { newFacts, existingFacts = [], publishedFacts = [] } = opts;

  const intra = detectIntraDocConflicts(newFacts);
  const inter = detectInterDocConflicts([...newFacts, ...existingFacts]);
  const version = detectVersionConflicts(newFacts, publishedFacts);

  return [...intra, ...inter, ...version];
}
