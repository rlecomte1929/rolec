import { describe, it, expect } from 'vitest';
import {
  isPetRelocationAvailableForCorridor,
  PET_RELOCATION_UNSUPPORTED_CORRIDORS,
} from '../petCorridorAvailability';

describe('isPetRelocationAvailableForCorridor', () => {
  it('defaults to available for a normal corridor (empty unsupported set)', () => {
    expect(isPetRelocationAvailableForCorridor('FR', 'DE')).toBe(true);
  });

  it('treats a missing destination as available (never block on unknown data)', () => {
    expect(isPetRelocationAvailableForCorridor('FR', undefined)).toBe(true);
    expect(isPetRelocationAvailableForCorridor(undefined, '')).toBe(true);
  });

  it('returns false for a corridor explicitly marked unsupported', () => {
    const unsupported = new Set(['FR-JP']);
    expect(isPetRelocationAvailableForCorridor('FR', 'JP', unsupported)).toBe(false);
    // A different corridor with the same destination stays available.
    expect(isPetRelocationAvailableForCorridor('DE', 'JP', unsupported)).toBe(true);
  });

  it('matches corridor keys case-insensitively', () => {
    const unsupported = new Set(['FR-JP']);
    expect(isPetRelocationAvailableForCorridor('fr', 'jp', unsupported)).toBe(false);
  });

  it('ships with an empty unsupported set (broadly available by default)', () => {
    expect(PET_RELOCATION_UNSUPPORTED_CORRIDORS.size).toBe(0);
  });
});
