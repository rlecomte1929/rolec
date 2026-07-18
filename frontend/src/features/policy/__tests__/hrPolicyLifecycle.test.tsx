import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  mockPolicyState,
  resolveLayoutModelFromState,
  renderHrPolicyLayout,
} from './hrPolicyTestUtils';
import type { HrPolicyWorkspaceResolved } from '../hrPolicyWorkspaceState';
import { buildEmployeePreviewCompare } from '../hrPolicyEmployeePreviewCompare';
import {
  derivePublishedComparisonSummary,
  deriveWorkingVersionComparisonSummary,
} from '../hrPolicyWorkspaceState';
import { deriveHrPolicyLifecycleContext } from '../hrPolicyLifecycle';
import { HrPolicyWorkspaceLayout } from '../HrPolicyWorkspaceLayout';

afterEach(() => {
  cleanup();
});

// AIQ-1600: the "What this means for employees" card (impact summary, primary
// CTA row, per-employee compare panels, replacement-draft warning) was removed
// from HrPolicyWorkspaceLayout per admin feedback. These tests now assert the
// surviving sections: the starter onboarding card (no_policy), the "Working
// draft" / "Replacement draft (not live)" panel (section C), and the "Active
// policy (live)" card (section B). Publish wiring is exercised where it now
// lives (HrPolicyReviewWorkspace), not in this presentational layout.
describe('HR policy lifecycle (product states)', () => {
  describe('A. no_policy', () => {
    it('shows starter onboarding, no publish CTA, no employee comparison block', () => {
      const model = resolveLayoutModelFromState('no_policy');
      expect(model.resolved.phase).toBe('no_policy');
      render(renderHrPolicyLayout(model));
      expect(document.getElementById('hr-policy-starter-onboarding')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^publish policy$/i })).not.toBeInTheDocument();
      expect(screen.queryByTestId('hr-policy-employee-compare')).not.toBeInTheDocument();
    });
  });

  describe('B. draft_not_publishable', () => {
    it('shows the Working draft panel, no publish CTA, no replacement warning without live published row', () => {
      const model = resolveLayoutModelFromState('draft_not_publishable');
      expect(model.resolved.phase).toBe('draft_not_publishable');
      render(renderHrPolicyLayout(model));
      expect(screen.getByText(/Working draft/i)).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^publish policy$/i })).not.toBeInTheDocument();
      expect(screen.queryByTestId('hr-policy-employee-compare')).not.toBeInTheDocument();
    });

    it('when a published policy exists, replacement path is distinct (published + replacement state)', () => {
      const replacement = resolveLayoutModelFromState('published_replacement_draft');
      expect(replacement.resolved.hasUnpublishedDraftAhead).toBe(true);
      expect(replacement.resolved.phase).toBe('published');
      render(renderHrPolicyLayout(replacement));
      expect(screen.getByText(/Replacement draft \(not live\)/i)).toBeInTheDocument();
    });
  });

  describe('D. published (no replacement draft)', () => {
    it('shows live policy card without replacement messaging', () => {
      const model = resolveLayoutModelFromState('published');
      expect(model.resolved.phase).toBe('published');
      expect(model.resolved.hasUnpublishedDraftAhead).toBe(false);
      render(renderHrPolicyLayout(model));
      expect(screen.getByText(/Active policy \(live\)/i)).toBeInTheDocument();
      expect(screen.queryByTestId('hr-policy-employee-compare')).not.toBeInTheDocument();
      expect(screen.queryByText(/Replacement draft/i)).not.toBeInTheDocument();
    });
  });

  describe('E. published + replacement draft', () => {
    it('shows the Replacement draft (not live) panel', () => {
      const model = resolveLayoutModelFromState('published_replacement_draft');
      expect(model.resolved.hasUnpublishedDraftAhead).toBe(true);
      render(renderHrPolicyLayout(model));
      expect(screen.getByText(/Replacement draft \(not live\)/i)).toBeInTheDocument();
    });
  });

  describe('Starter template path', () => {
    it('starter_template_draft resolves to draft_not_publishable with template-backed policy', () => {
      const { policies, normalized, policyReview } = mockPolicyState('starter_template_draft');
      const model = resolveLayoutModelFromState('starter_template_draft');
      expect(model.resolved.phase).toBe('draft_not_publishable');
      expect(normalized?.policy).toMatchObject({ template_name: 'starter_standard' });
      expect(policies.length).toBe(1);
      expect(policyReview).toBeTruthy();
    });
  });
});

describe('Operational copy hygiene (no internal jargon in HR workspace strings)', () => {
  it('layout copy for published state avoids layer/normalization codes', () => {
    const model = resolveLayoutModelFromState('published');
    const { container } = render(renderHrPolicyLayout(model));
    const text = container.textContent?.toLowerCase() ?? '';
    expect(text).not.toMatch(/\blayer[\s_-]?2\b/);
    expect(text).not.toMatch(/\bjson\b.*\bpayload\b/);
  });
});

describe('Edge: partial resolver output still drives the draft panel', () => {
  it('shows the Working draft panel when phase stays draft_not_publishable', () => {
    const synthetic: HrPolicyWorkspaceResolved = {
      phase: 'draft_not_publishable',
      hasUnpublishedDraftAhead: false,
      comparisonSummary: 'informational',
      comparisonBlockers: [],
      publishReadiness: { status: 'blocked' },
      comparisonReadiness: null,
      normalizationReadiness: null,
      highlightIssues: [],
      publishedTitle: 'X',
      publishedVersionNumber: null,
      draftVersionNumber: 1,
      benefitRuleCount: 1,
      exclusionCount: 0,
      draftRuleCandidatesCount: 0,
    };
    const { normalized, policyReview } = mockPolicyState('draft_not_publishable');
    const lifecycle = deriveHrPolicyLifecycleContext(normalized, synthetic);
    const publishedComparison = derivePublishedComparisonSummary(normalized);
    const workingComparison = deriveWorkingVersionComparisonSummary(normalized);
    const employeePreviewCompare = buildEmployeePreviewCompare({
      resolved: synthetic,
      draftEntitlementPreview: Array.isArray(policyReview?.entitlement_effective_preview)
        ? (policyReview!.entitlement_effective_preview as Array<Record<string, unknown>>)
        : [],
      publishedComparison,
      workingComparison,
    });
    const noop = () => {};
    render(
      <HrPolicyWorkspaceLayout
        resolved={synthetic}
        lifecycle={lifecycle}
        documentsCount={0}
        loading={false}
        reviewUnavailable={false}
        starterTemplateBusy={null}
        starterError={null}
        onSelectStarterTemplate={noop}
        onUploadDocument={noop}
        onReviewDraft={noop}
        onReviewDraftReplacement={noop}
        onScrollToStarterBaselines={noop}
        onAdjustBenefits={noop}
        onRequestPublishPreflight={noop}
        employeePreviewCompare={employeePreviewCompare}
      />
    );
    expect(screen.getByText(/Working draft/i)).toBeInTheDocument();
  });
});
