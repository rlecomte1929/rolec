import { describe, expect, it } from 'vitest';
import { resolveMobilityCaseIdForSummary } from './mobilityCaseIdResolution';

describe('resolveMobilityCaseIdForSummary', () => {
  it('prefers backend mobility_case_id over query and env', () => {
    expect(
      resolveMobilityCaseIdForSummary({
        backendMobilityCaseId: 'aaaaaaaa-bbbb-4ccc-dddd-eeeeeeeeeeee',
        debugQueryMcid: 'bbbbbbbb-bbbb-4ccc-dddd-ffffffffffff',
        devDemoEnvMobilityCaseId: 'cccccccc-cccc-4ccc-dddd-gggggggggggg',
        isDev: true,
      }),
    ).toBe('aaaaaaaa-bbbb-4ccc-dddd-eeeeeeeeeeee');
  });

  it('uses ?mcid= when backend is empty', () => {
    expect(
      resolveMobilityCaseIdForSummary({
        backendMobilityCaseId: null,
        debugQueryMcid: '  qqqqqqqq-qqqq-4qqq-qqqq-qqqqqqqqqqqq  ',
        devDemoEnvMobilityCaseId: 'cccccccc-cccc-4ccc-dddd-gggggggggggg',
        isDev: true,
      }),
    ).toBe('qqqqqqqq-qqqq-4qqq-qqqq-qqqqqqqqqqqq');
  });

  it('does not use demo env when not dev', () => {
    expect(
      resolveMobilityCaseIdForSummary({
        backendMobilityCaseId: null,
        debugQueryMcid: null,
        devDemoEnvMobilityCaseId: 'cccccccc-cccc-4ccc-dddd-gggggggggggg',
        isDev: false,
      }),
    ).toBeNull();
  });

  it('uses demo env only in dev when higher-priority sources are empty', () => {
    expect(
      resolveMobilityCaseIdForSummary({
        backendMobilityCaseId: '',
        debugQueryMcid: undefined,
        devDemoEnvMobilityCaseId: 'cccccccc-cccc-4ccc-dddd-gggggggggggg',
        isDev: true,
      }),
    ).toBe('cccccccc-cccc-4ccc-dddd-gggggggggggg');
  });
});
