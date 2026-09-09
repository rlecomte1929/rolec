/**
 * Characterisation of the policyBuilderAPI client surface before splitting client.ts (WS3 Task 3.8 slice 5).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import { policyBuilderAPI as policyBuilderAPIFromModule } from '../policyBuilderApi';
import { policyBuilderAPI } from '../client';

const POLICY_BUILDER_API_METHODS = ['getTemplates'] as const;

describe('policyBuilderAPI surface', () => {
  it('exposes the characterised method names', () => {
    expect(Object.keys(policyBuilderAPI).sort()).toEqual([...POLICY_BUILDER_API_METHODS].sort());
  });

  it('re-exports the same object as policyBuilderApi.ts', () => {
    expect(policyBuilderAPI).toBe(policyBuilderAPIFromModule);
  });
});
