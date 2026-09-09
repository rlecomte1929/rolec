import { describe, it, expect } from 'vitest';
import { policyLandingMode } from '../HrPolicyPageV2';

describe('policyLandingMode', () => {
  it('is error-only when the workspace failed to load', () => {
    expect(policyLandingMode('Unable to load your policy. Try again or contact support.')).toBe('error');
  });

  it('is workspace when there is no load error (empty onboarding allowed)', () => {
    expect(policyLandingMode(null)).toBe('workspace');
  });
});
