import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { HrPolicyDraftReviewPanel } from '../HrPolicyDraftReviewPanel';
import {
  mockPolicyReviewPayload,
  mockPolicyState,
  resolveLayoutModelFromState,
} from './hrPolicyTestUtils';
import { resolveHrPolicyWorkspaceState } from '../hrPolicyWorkspaceState';
import { buildEmployeePreviewCompare } from '../hrPolicyEmployeePreviewCompare';
import {
  derivePublishedComparisonSummary,
  deriveWorkingVersionComparisonSummary,
} from '../hrPolicyWorkspaceState';

afterEach(() => cleanup());

describe('Draft flow — review panel', () => {
  it('shows document summary, draft review heading, and checklist issues for a blocked draft', () => {
    const model = resolveLayoutModelFromState('draft_not_publishable');
    const review = mockPolicyReviewPayload({
      issues: [
        { message: 'Add a clear cap for household goods shipment.', tier: 'comparison' },
        { message: 'Confirm eligibility for short-term routes.', tier: 'publish' },
      ],
    });
    const withSource = {
      ...review,
      source_document: { filename: 'relocation-policy-2025.pdf', processing_status: 'ready' },
    };

    render(
      <HrPolicyDraftReviewPanel
        policyReview={withSource}
        workspaceResolved={model.resolved}
        versionStatus="draft"
        reviewLoading={false}
      />
    );

    expect(screen.getByText(/Policy draft review/i)).toBeInTheDocument();
    expect(screen.getByText(/relocation-policy-2025\.pdf/)).toBeInTheDocument();
    expect(screen.getByText(/What to fix before going live/i)).toBeInTheDocument();
    expect(screen.getByText(/Add a clear cap for household goods shipment/i)).toBeInTheDocument();
  });

  it('shows loading skeleton while review payload is loading', () => {
    const model = resolveLayoutModelFromState('draft_not_publishable');
    render(
      <HrPolicyDraftReviewPanel
        policyReview={null}
        workspaceResolved={model.resolved}
        versionStatus="draft"
        reviewLoading
      />
    );
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders nothing when workspace phase is no_policy', () => {
    const model = resolveLayoutModelFromState('no_policy');
    const { container } = render(
      <HrPolicyDraftReviewPanel
        policyReview={mockPolicyReviewPayload()}
        workspaceResolved={model.resolved}
        versionStatus="draft"
      />
    );
    expect(container.firstChild).toBeNull();
  });
});

describe('Draft flow — upload → draft (resolver + copy)', () => {
  it('draft_not_publishable state surfaces blocked publish readiness without live policy', () => {
    const { policies, normalized, policyReview } = mockPolicyState('draft_not_publishable');
    const resolved = resolveHrPolicyWorkspaceState({ policies, normalized, policyReview });
    expect(resolved.phase).toBe('draft_not_publishable');
    expect(resolved.hasUnpublishedDraftAhead).toBe(false);
    expect(resolved.publishReadiness?.status).toBe('blocked');
  });
});

describe('HR override impact (preview model)', () => {
  it('future employee preview rows follow entitlement_effective_preview (simulating post-override payload)', () => {
    const model = resolveLayoutModelFromState('ready_to_publish');
    const basePreview = [
      {
        benefit_key: 'housing',
        label: 'Housing',
        effective: { max_value: 1000, currency: 'USD' },
      },
    ];
    const adjustedPreview = [
      {
        benefit_key: 'housing',
        label: 'Housing',
        effective: { max_value: 2500, currency: 'USD' },
      },
    ];
    const pub = derivePublishedComparisonSummary(mockPolicyState('ready_to_publish').normalized);
    const work = deriveWorkingVersionComparisonSummary(mockPolicyState('ready_to_publish').normalized);

    const before = buildEmployeePreviewCompare({
      resolved: model.resolved,
      draftEntitlementPreview: basePreview as unknown as Array<Record<string, unknown>>,
      publishedComparison: pub,
      workingComparison: work,
    });
    const after = buildEmployeePreviewCompare({
      resolved: model.resolved,
      draftEntitlementPreview: adjustedPreview as unknown as Array<Record<string, unknown>>,
      publishedComparison: pub,
      workingComparison: work,
    });

    expect(before.future?.previewRows[0]).toMatchObject({
      effective: expect.objectContaining({ max_value: 1000 }),
    });
    expect(after.future?.previewRows[0]).toMatchObject({
      effective: expect.objectContaining({ max_value: 2500 }),
    });
  });
});

describe('Partial API payloads', () => {
  it('resolver tolerates minimal normalized object', () => {
    const minimal = {
      policy: { title: 'T' },
      version: { id: 'v1', version_number: 1, status: 'draft' },
      benefit_rules: [],
      exclusions: [],
    };
    const resolved = resolveHrPolicyWorkspaceState({
      policies: [{ id: 'p1' }],
      normalized: minimal,
      policyReview: null,
    });
    expect(resolved.phase).toBe('draft_not_publishable');
    expect(resolved.benefitRuleCount).toBe(0);
  });
});
