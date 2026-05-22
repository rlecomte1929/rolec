/**
 * [P2-5] Tests for conflict_detector.ts
 *
 * Validation criteria from Notion:
 * ✓ Synthetic test set with 3 planted contradictions — all 3 detected
 * ✓ Zero false positives on a clean document set
 * ✓ Conflict report includes exact page references for both conflicting values
 * ✓ High severity = monetary contradiction; medium = condition-only contradiction
 */
import { describe, expect, it } from 'vitest';
import {
  detectIntraDocConflicts,
  detectInterDocConflicts,
  detectVersionConflicts,
  detectAllConflicts,
} from '../conflict_detector';
import type { PolicyFactInput } from '../conflict_detector';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MANAGER_HOUSING_3000: PolicyFactInput = {
  id: 'fact-1',
  category_code: 'CAT-01',
  tier: 'Manager',
  normalized_value: { value: '3000', currency: 'EUR', unit: 'month' },
  source_doc: 'Policy2024.pdf',
  source_page: 5,
  snapshot_id: 'snap-a',
};

const MANAGER_HOUSING_3500: PolicyFactInput = {
  id: 'fact-2',
  category_code: 'CAT-01',
  tier: 'Manager',
  normalized_value: { value: '3500', currency: 'EUR', unit: 'month' },
  source_doc: 'Policy2024.pdf',
  source_page: 12,
  snapshot_id: 'snap-a',
};

const DIRECTOR_HOUSING_5000_DOCB: PolicyFactInput = {
  id: 'fact-3',
  category_code: 'CAT-01',
  tier: 'Director',
  normalized_value: { value: '5000', currency: 'EUR', unit: 'month' },
  source_doc: 'PolicyDraft2025.pdf',
  source_page: 3,
  snapshot_id: 'snap-b',
};

const DIRECTOR_HOUSING_4000_DOCA: PolicyFactInput = {
  id: 'fact-4',
  category_code: 'CAT-01',
  tier: 'Director',
  normalized_value: { value: '4000', currency: 'EUR', unit: 'month' },
  source_doc: 'Policy2024.pdf',
  source_page: 6,
  snapshot_id: 'snap-a',
};

const MANAGER_HOUSING_3500_DOCB: PolicyFactInput = {
  id: 'fact-5',
  category_code: 'CAT-01',
  tier: 'Manager',
  normalized_value: { value: '3500', currency: 'EUR', unit: 'month' },
  source_doc: 'PolicyDraft2025.pdf',
  source_page: 8,
  snapshot_id: 'snap-b',
};

const MANAGER_HOUSING_3000_DOCB: PolicyFactInput = {
  id: 'fact-6',
  category_code: 'CAT-01',
  tier: 'Manager',
  normalized_value: { value: '3000', currency: 'EUR', unit: 'month' },
  source_doc: 'PolicyDraft2025.pdf',
  source_page: 10,
  snapshot_id: 'snap-b',
};

// Clean fact — no contradiction anywhere
const VP_TRAVEL_CLEAN: PolicyFactInput = {
  id: 'fact-7',
  category_code: 'CAT-05',
  tier: 'VP',
  normalized_value: { value: '10000', currency: 'EUR', unit: 'year' },
  source_doc: 'Policy2024.pdf',
  source_page: 20,
  snapshot_id: 'snap-a',
};

// Same value but different conditions → medium
const MANAGER_HOUSING_3500_COND_A: PolicyFactInput = {
  id: 'fact-8',
  category_code: 'CAT-01',
  tier: 'Manager',
  normalized_value: { value: '3500', currency: 'EUR', condition: 'on-site role' },
  source_doc: 'PolicyDraft2025.pdf',
  source_page: 5,
};

const MANAGER_HOUSING_3500_COND_B: PolicyFactInput = {
  id: 'fact-9',
  category_code: 'CAT-01',
  tier: 'Manager',
  normalized_value: { value: '3500', currency: 'EUR', condition: 'remote role' },
  source_doc: 'PolicyDraft2025.pdf',
  source_page: 14,
};

// ---------------------------------------------------------------------------
// Intra-document conflicts
// ---------------------------------------------------------------------------

describe('detectIntraDocConflicts', () => {
  it('VC-1: detects planted intra-doc contradiction (same doc, same category+tier, different value)', () => {
    // fact-1 (p.5: 3000) vs fact-2 (p.12: 3500) — same doc, same category+tier
    const conflicts = detectIntraDocConflicts([MANAGER_HOUSING_3000, MANAGER_HOUSING_3500]);
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].severity).toBe('high');
    expect(conflicts[0].conflict_type).toBe('intra_document');
  });

  it('includes exact page references for both conflicting values', () => {
    const conflicts = detectIntraDocConflicts([MANAGER_HOUSING_3000, MANAGER_HOUSING_3500]);
    expect(conflicts[0].value_a.page).toBe(5);
    expect(conflicts[0].value_b.page).toBe(12);
  });

  it('VC: zero false positives on a clean set', () => {
    const clean: PolicyFactInput[] = [
      MANAGER_HOUSING_3000,
      VP_TRAVEL_CLEAN,
      DIRECTOR_HOUSING_4000_DOCA,
    ];
    expect(detectIntraDocConflicts(clean)).toHaveLength(0);
  });

  it('detects medium severity for same value with different conditions', () => {
    const conflicts = detectIntraDocConflicts([
      MANAGER_HOUSING_3500_COND_A,
      MANAGER_HOUSING_3500_COND_B,
    ]);
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].severity).toBe('medium');
  });

  it('does not self-compare (same id)', () => {
    const fact = { ...MANAGER_HOUSING_3000 };
    expect(detectIntraDocConflicts([fact, fact])).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Inter-document conflicts
// ---------------------------------------------------------------------------

describe('detectInterDocConflicts', () => {
  it('VC-2: detects planted inter-doc contradiction (two docs disagree on Director housing)', () => {
    // fact-3 (PolicyDraft2025, 5000) vs fact-4 (Policy2024, 4000) — same category+tier
    const conflicts = detectInterDocConflicts([
      DIRECTOR_HOUSING_5000_DOCB,
      DIRECTOR_HOUSING_4000_DOCA,
    ]);
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].severity).toBe('high');
    expect(conflicts[0].conflict_type).toBe('inter_document');
  });

  it('includes source_doc in both conflict values', () => {
    const conflicts = detectInterDocConflicts([
      DIRECTOR_HOUSING_5000_DOCB,
      DIRECTOR_HOUSING_4000_DOCA,
    ]);
    const docs = new Set([conflicts[0].value_a.source_doc, conflicts[0].value_b.source_doc]);
    expect(docs.has('PolicyDraft2025.pdf')).toBe(true);
    expect(docs.has('Policy2024.pdf')).toBe(true);
  });

  it('VC: zero false positives — same value in two docs → no conflict', () => {
    const same: PolicyFactInput[] = [
      MANAGER_HOUSING_3500,                  // Policy2024, p.12: 3500
      MANAGER_HOUSING_3500_DOCB,             // PolicyDraft2025, p.8: 3500 (different doc)
    ];
    expect(detectInterDocConflicts(same)).toHaveLength(0);
  });

  it('skips intra-doc pairs (same source_doc)', () => {
    // fact-1 and fact-2 are both from Policy2024 — should not appear as inter-doc
    const conflicts = detectInterDocConflicts([MANAGER_HOUSING_3000, MANAGER_HOUSING_3500]);
    expect(conflicts).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// Version conflicts
// ---------------------------------------------------------------------------

describe('detectVersionConflicts', () => {
  it('VC-3: detects planted version conflict (new upload contradicts published policy)', () => {
    // New doc says Manager housing = 3000; published policy says 3500
    const conflicts = detectVersionConflicts(
      [MANAGER_HOUSING_3000_DOCB],   // new
      [MANAGER_HOUSING_3500],        // published (Policy2024)
    );
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].severity).toBe('high');
    expect(conflicts[0].conflict_type).toBe('version_conflict');
  });

  it('no conflict when new upload matches published value', () => {
    const conflicts = detectVersionConflicts(
      [MANAGER_HOUSING_3500_DOCB],   // new: 3500
      [MANAGER_HOUSING_3500],        // published: 3500
    );
    expect(conflicts).toHaveLength(0);
  });

  it('no conflict when category not in published policy', () => {
    const conflicts = detectVersionConflicts(
      [VP_TRAVEL_CLEAN],             // new (CAT-05 VP)
      [MANAGER_HOUSING_3500],        // published (CAT-01 Manager)
    );
    expect(conflicts).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// detectAllConflicts — combined 3-planted-contradictions test
// ---------------------------------------------------------------------------

describe('detectAllConflicts — 3-contradiction synthetic set', () => {
  it('detects all 3 planted contradictions', () => {
    // Contradiction 1 (intra-doc): Policy2024 has Manager housing at 3000 (p.5) and 3500 (p.12)
    // Contradiction 2 (inter-doc): Policy2024 has Director housing at 4000; Draft2025 has 5000
    // Contradiction 3 (version): Draft2025 has Manager housing at 3000; published says 3500
    const allConflicts = detectAllConflicts({
      newFacts: [
        MANAGER_HOUSING_3000,    // Policy2024 p.5 — contradiction 1 (intra)
        MANAGER_HOUSING_3500,    // Policy2024 p.12 — contradiction 1 (intra)
        MANAGER_HOUSING_3000_DOCB, // Draft2025 — contradiction 3 (version)
        DIRECTOR_HOUSING_5000_DOCB, // Draft2025 — contradiction 2 (inter)
      ],
      existingFacts: [
        DIRECTOR_HOUSING_4000_DOCA, // Policy2024 — part of contradiction 2
      ],
      publishedFacts: [
        MANAGER_HOUSING_3500,   // published: Manager housing = 3500
      ],
    });

    // All 3 contradiction types should be represented
    const types = new Set(allConflicts.map((c) => c.conflict_type));
    expect(types.has('intra_document')).toBe(true);
    expect(types.has('inter_document')).toBe(true);
    expect(types.has('version_conflict')).toBe(true);
    // At least 3 distinct conflicts
    expect(allConflicts.length).toBeGreaterThanOrEqual(3);
  });

  it('zero false positives on a fully consistent set', () => {
    const cleanFact: PolicyFactInput = {
      id: 'clean-1',
      category_code: 'CAT-10',
      tier: 'Manager',
      normalized_value: { value: '2000', currency: 'EUR' },
      source_doc: 'CleanPolicy.pdf',
      source_page: 1,
    };
    const conflicts = detectAllConflicts({
      newFacts: [cleanFact],
      existingFacts: [],
      publishedFacts: [],
    });
    expect(conflicts).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// ConflictReport shape
// ---------------------------------------------------------------------------

describe('ConflictReport structure', () => {
  it('includes conflict_id, category_code, tier, severity, detected_at', () => {
    const conflicts = detectIntraDocConflicts([MANAGER_HOUSING_3000, MANAGER_HOUSING_3500]);
    const report = conflicts[0];
    expect(report.conflict_id).toBeTruthy();
    expect(report.category_code).toBe('CAT-01');
    expect(report.tier).toBe('Manager');
    expect(['high', 'medium']).toContain(report.severity);
    expect(report.detected_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });
});
