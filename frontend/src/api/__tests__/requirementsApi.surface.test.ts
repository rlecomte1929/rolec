/**
 * Characterisation of the requirementsAPI client surface before splitting client.ts (WS3 Task 3.8 slice 4).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import { requirementsAPI as requirementsAPIFromModule } from '../requirementsApi';
import { requirementsAPI } from '../client';

const REQUIREMENTS_API_METHODS = ['getSufficiency'] as const;

describe('requirementsAPI surface', () => {
  it('exposes the characterised method names', () => {
    expect(Object.keys(requirementsAPI).sort()).toEqual([...REQUIREMENTS_API_METHODS].sort());
  });

  it('re-exports the same object as requirementsApi.ts', () => {
    expect(requirementsAPI).toBe(requirementsAPIFromModule);
  });
});
