import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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

describe('HR policy lifecycle (product states)', () => {
  describe('A. no_policy', () => {
    it('shows starter onboarding, no publish CTA, no employee comparison block', () => {
      const model = resolveLayoutModelFromState('no_policy');
      expect(model.resolved.phase).toBe('no_policy');
      render(renderHrPolicyLayout(model));
      expect(screen.getByText(/Get your relocation policy in place/i)).toBeInTheDocument();
      expect(document.getElementById('hr-policy-starter-onboarding')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^publish policy$/i })).not.toBeInTheDocument();
      expect(screen.queryByTestId('hr-policy-employee-compare')).not.toBeInTheDocument();
    });
  });

  describe('B. draft_not_publishable', () => {
    it('shows draft-phase headline, Review draft as primary, future preview, no replacement warning without live published row', () => {
      const model = resolveLayoutModelFromState('draft_not_publishable');
      expect(model.resolved.phase).toBe('draft_not_publishable');
      render(renderHrPolicyLayout(model));
      expect(screen.getByText(/Draft saved—finish review before it goes live/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /review draft/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^publish policy$/i })).not.toBeInTheDocument();
      expect(screen.getByTestId('hr-policy-panel-if-publish')).toBeInTheDocument();
      expect(screen.queryByTestId('hr-policy-replacement-warning')).not.toBeInTheDocument();
    });

    it('when a published policy exists, replacement path is distinct (published + replacement state)', () => {
      const replacement = resolveLayoutModelFromState('published_replacement_draft');
      expect(replacement.resolved.hasUnpublishedDraftAhead).toBe(true);
      expect(replacement.resolved.phase).toBe('published');
      render(renderHrPolicyLayout(replacement));
      expect(screen.getByTestId('hr-policy-replacement-warning')).toBeInTheDocument();
    });
  });

  describe('C. ready_to_publish', () => {
    it('shows publish CTA, readiness badge, opens preflight when callback provided', () => {
      const onPreflight = vi.fn();
      const model = resolveLayoutModelFromState('ready_to_publish');
      expect(model.resolved.phase).toBe('ready_to_publish');
      render(
        renderHrPolicyLayout(model, {
          onRequestPublishPreflight: onPreflight,
        })
      );
      expect(screen.getByText(/Ready to publish—not live yet/i)).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /publish policy/i }));
      expect(onPreflight).toHaveBeenCalledTimes(1);
    });
  });

  describe('D. published (no replacement draft)', () => {
    it('shows live policy card and employee compare without replacement messaging', () => {
      const model = resolveLayoutModelFromState('published');
      expect(model.resolved.phase).toBe('published');
      expect(model.resolved.hasUnpublishedDraftAhead).toBe(false);
      render(renderHrPolicyLayout(model));
      expect(screen.getByText(/Active policy \(live\)/i)).toBeInTheDocument();
      expect(screen.getByText(/This published version is what relocating employees see today/i)).toBeInTheDocument();
      expect(screen.getByTestId('hr-policy-employee-compare')).toBeInTheDocument();
      expect(screen.getByTestId('hr-policy-panel-current-employee')).toBeInTheDocument();
      expect(screen.queryByTestId('hr-policy-panel-if-publish')).not.toBeInTheDocument();
      expect(screen.queryByTestId('hr-policy-replacement-warning')).not.toBeInTheDocument();
      expect(screen.queryByText(/Replacement draft/i)).not.toBeInTheDocument();
    });
  });

  describe('E. published + replacement draft', () => {
    it('shows replacement warning, both compare panels, Review new draft CTA', () => {
      const model = resolveLayoutModelFromState('published_replacement_draft');
      expect(model.resolved.hasUnpublishedDraftAhead).toBe(true);
      render(renderHrPolicyLayout(model));
      expect(screen.getByTestId('hr-policy-replacement-warning')).toBeInTheDocument();
      expect(screen.getByTestId('hr-policy-panel-current-employee')).toBeInTheDocument();
      expect(screen.getByTestId('hr-policy-panel-if-publish')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /review new draft/i })).toBeInTheDocument();
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

describe('Edge: partial resolver output still drives draft headline', () => {
  it('shows draft banner when phase stays draft_not_publishable', () => {
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
    expect(screen.getByText(/Draft saved—finish review before it goes live/i)).toBeInTheDocument();
  });
});
