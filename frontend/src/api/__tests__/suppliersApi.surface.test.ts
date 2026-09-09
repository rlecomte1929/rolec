/**
 * Characterisation of the suppliers + prompts API cluster before splitting client.ts (WS3 Task 3.8 slice 8).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import {
  promptsAPI as promptsAPIFromModule,
  suppliersAPI as suppliersAPIFromModule,
} from '../suppliersApi';
import { promptsAPI, suppliersAPI } from '../client';

const SUPPLIERS_API_METHODS = [
  'list',
  'get',
  'listPendingCapabilities',
  'search',
  'getCategories',
  'getCountries',
  'create',
  'update',
  'setStatus',
  'addCapability',
  'updateCapability',
  'removeCapability',
  'approveCapability',
  'rejectCapability',
  'updateScoring',
  'getRankingDebug',
] as const;

const PROMPTS_API_METHODS = [
  'list',
  'listForTask',
  'create',
  'promote',
  'setCanaryShare',
  'winRates',
] as const;

describe('suppliers API cluster surface', () => {
  it('exposes the characterised suppliersAPI method names', () => {
    expect(Object.keys(suppliersAPI).sort()).toEqual([...SUPPLIERS_API_METHODS].sort());
  });

  it('re-exports the same suppliersAPI object as suppliersApi.ts', () => {
    expect(suppliersAPI).toBe(suppliersAPIFromModule);
  });

  it('exposes the characterised promptsAPI method names', () => {
    expect(Object.keys(promptsAPI).sort()).toEqual([...PROMPTS_API_METHODS].sort());
  });

  it('re-exports the same promptsAPI object as suppliersApi.ts', () => {
    expect(promptsAPI).toBe(promptsAPIFromModule);
  });
});
