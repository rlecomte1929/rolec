import { describe, it, expect } from 'vitest';
import {
  resolveHrPolicyWorkspaceState,
  shouldOfferFreshPolicyBuild,
} from '../hrPolicyWorkspaceState';

// AIQ-1015 — the HR policy page must never show the live-policy state AND the
// no-policy "Start your policy" onboarding at the same time.

describe('AIQ-1015 — live / no-policy mutual exclusivity', () => {
  describe('resolveHrPolicyWorkspaceState: published wins over no_policy', () => {
    it('a published version with NO company_policies row resolves to published (not no_policy)', () => {
      // matrix-only / versions-only deployment: no company_policies row, but a published version exists.
      const resolved = resolveHrPolicyWorkspaceState({
        policies: [],
        normalized: { published_version: { id: 'v1', status: 'published' } },
        policyReview: null,
      });
      expect(resolved.phase).toBe('published');
    });

    it('a truly empty company (no policy, no published version) resolves to no_policy', () => {
      const resolved = resolveHrPolicyWorkspaceState({
        policies: [],
        normalized: {},
        policyReview: null,
      });
      expect(resolved.phase).toBe('no_policy');
    });
  });

  describe('shouldOfferFreshPolicyBuild: onboarding doors never co-render with a live policy', () => {
    it('hides the doors when there is a live policy (canonical OR matrix)', () => {
      expect(shouldOfferFreshPolicyBuild(true, false)).toBe(false);
    });

    it('shows the doors only for a true no-policy company with no draft in flight', () => {
      expect(shouldOfferFreshPolicyBuild(false, false)).toBe(true);
    });

    it('hides the doors while a draft is in progress', () => {
      expect(shouldOfferFreshPolicyBuild(false, true)).toBe(false);
      expect(shouldOfferFreshPolicyBuild(true, true)).toBe(false);
    });
  });
});
