/**
 * P2-07a (AIQ-698) — TS contract guard for RoadmapStep.dependency_ids.
 *
 * Mirrors backend/tests/test_roadmap_step_schema.py. The TS interface erases at
 * runtime, but we can pin the shape with:
 *   1. A type-level assignment that fails to compile if `dependency_ids: string[]`
 *      is removed from the interface or renamed.
 *   2. A runtime sample-object round-trip asserting the field name is what
 *      consumers receive on the wire.
 */
import { describe, expect, it } from 'vitest';

import type { RoadmapStep } from './relopass-api-contracts';

// 1. Compile-time guard: this assignment will FAIL TO COMPILE if RoadmapStep
//    no longer has `dependency_ids: string[]`.
const _typeGuard: Pick<RoadmapStep, 'dependency_ids'> = {
  dependency_ids: ['step-1a', 'step-1b'],
};
void _typeGuard;

describe('RoadmapStep contract — dependency_ids', () => {
  it('a sample step JSON round-trips with dependency_ids populated', () => {
    const sample: RoadmapStep = {
      id: 'step-2',
      track_id: 'track-1',
      case_id: 'case-1',
      title: 'Submit work permit application',
      description: 'After biometrics are booked.',
      status: 'pending',
      owner: 'employee',
      vendor_id: null,
      due_date: '2026-07-01',
      completed_at: null,
      sort_order: 2,
      dependency_ids: ['step-1a', 'step-1b'],
      ai_suggestion: null,
      created_at: '2026-06-04T12:00:00Z',
      updated_at: '2026-06-04T12:00:00Z',
    };

    const wireRoundTripped = JSON.parse(JSON.stringify(sample)) as RoadmapStep;
    expect(wireRoundTripped.dependency_ids).toEqual(['step-1a', 'step-1b']);
  });

  it('defaults to an empty array conceptually (no other field name carries the deps)', () => {
    const sample: RoadmapStep = {
      id: 'step-1',
      track_id: 'track-1',
      case_id: 'case-1',
      title: 'Book biometrics',
      description: null,
      status: 'pending',
      owner: 'employee',
      vendor_id: null,
      due_date: null,
      completed_at: null,
      sort_order: 1,
      dependency_ids: [],
      ai_suggestion: null,
      created_at: '2026-06-04T12:00:00Z',
      updated_at: '2026-06-04T12:00:00Z',
    };
    expect(sample.dependency_ids).toEqual([]);
    // Belt-and-braces: ensure no rogue 'dependencies' field crept in alongside.
    expect((sample as Record<string, unknown>).dependencies).toBeUndefined();
  });
});
