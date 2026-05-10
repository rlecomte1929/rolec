/**
 * Deterministic factories for HR policy + employee policy tests.
 * Shapes align with `resolveHrPolicyWorkspaceState`, `HrPolicyDraftReviewPanel`, and employee package API.
 */
import type { AssignmentPackagePolicyPayload } from '../EmployeePolicyPanel';
import {
  buildEmployeePreviewCompare,
} from '../hrPolicyEmployeePreviewCompare';
import { deriveHrPolicyLifecycleContext, type HrPolicyLifecycleContext } from '../hrPolicyLifecycle';
import type { HrPolicyWorkspaceLayoutProps } from '../HrPolicyWorkspaceLayout';
import { HrPolicyWorkspaceLayout } from '../HrPolicyWorkspaceLayout';
import {
  derivePublishedComparisonSummary,
  deriveWorkingVersionComparisonSummary,
  resolveHrPolicyWorkspaceState,
  type HrPolicyWorkspaceResolved,
} from '../hrPolicyWorkspaceState';
import React from 'react';

export type MockPolicyStateType =
  | 'no_policy'
  | 'starter_template_draft'
  | 'draft_not_publishable'
  | 'ready_to_publish'
  | 'published'
  | 'published_replacement_draft';

const POLICY_ID = 'cp-test-1';
const PUB_VER_ID = 'pv-1';
const DRAFT_VER_ID = 'pv-2';

/** Minimal company policy row (list endpoint). */
export function mockCompanyPolicyRow(overrides: Record<string, unknown> = {}) {
  return { id: POLICY_ID, title: 'Test relocation policy', ...overrides };
}

function baseNormalized(): Record<string, unknown> {
  return {
    policy: { id: POLICY_ID, title: 'Test relocation policy', template_source: 'default_platform_template', template_name: 'starter_standard' },
    version: {
      id: DRAFT_VER_ID,
      version_number: 2,
      status: 'draft',
      source_policy_document_id: 'doc-1',
    },
    benefit_rules: [{ id: 'br1', benefit_key: 'temporary_housing' }],
    exclusions: [],
    evidence_requirements: [],
    conditions: [],
    assignment_applicability: [],
    family_applicability: [],
    source_links: [],
  };
}

/**
 * Normalized payload + policies list for a high-level product state.
 * Use with `resolveHrPolicyWorkspaceState` / `deriveHrPolicyLifecycleContext`.
 */
export function mockPolicyState(type: MockPolicyStateType): {
  policies: Array<Record<string, unknown>>;
  normalized: Record<string, unknown> | null;
  policyReview: Record<string, unknown> | null;
} {
  switch (type) {
    case 'no_policy':
      return { policies: [], normalized: null, policyReview: null };

    case 'starter_template_draft': {
      const normalized = {
        ...baseNormalized(),
        published_version: undefined,
        policy_readiness: {
          publish_readiness: { status: 'blocked', issues: [{ message: 'Add effective date' }] },
          comparison_readiness: { status: 'blocked' },
        },
      };
      return {
        policies: [mockCompanyPolicyRow()],
        normalized,
        policyReview: mockPolicyReviewPayload({ document_title: 'Starter baseline' }),
      };
    }

    case 'draft_not_publishable': {
      const normalized = {
        ...baseNormalized(),
        policy_readiness: {
          publish_readiness: { status: 'blocked', issues: [{ message: 'Complete required benefit limits' }] },
          comparison_readiness: { status: 'blocked' },
        },
      };
      return {
        policies: [mockCompanyPolicyRow()],
        normalized,
        policyReview: mockPolicyReviewPayload(),
      };
    }

    case 'ready_to_publish': {
      const normalized = {
        ...baseNormalized(),
        policy_readiness: {
          publish_readiness: { status: 'ready' },
          comparison_readiness: { status: 'ready' },
        },
      };
      return {
        policies: [mockCompanyPolicyRow()],
        normalized,
        policyReview: mockPolicyReviewPayload({ entitlement_rows: [{ benefit_key: 'shipping', label: 'Shipping', max_value: 500, currency: 'USD' }] }),
      };
    }

    case 'published': {
      const normalized = {
        ...baseNormalized(),
        version: { id: PUB_VER_ID, version_number: 1, status: 'published', source_policy_document_id: null },
        published_version: { id: PUB_VER_ID, version_number: 1, status: 'published', source_policy_document_id: null },
        published_comparison_readiness: { comparison_ready: true },
        policy_readiness: {
          publish_readiness: { status: 'ready' },
          comparison_readiness: { status: 'ready' },
        },
      };
      return {
        policies: [mockCompanyPolicyRow()],
        normalized,
        policyReview: mockPolicyReviewPayload({
          employee_visibility: { employee_sees_published_policy_matrix: true },
          readiness: { comparison_rule_readiness: { comparison_ready_strict: true } },
        }),
      };
    }

    case 'published_replacement_draft': {
      const normalized = {
        ...baseNormalized(),
        version: { id: DRAFT_VER_ID, version_number: 2, status: 'draft', source_policy_document_id: 'doc-2' },
        published_version: { id: PUB_VER_ID, version_number: 1, status: 'published', source_policy_document_id: null },
        published_comparison_readiness: { comparison_ready: true },
        policy_readiness: {
          publish_readiness: { status: 'ready' },
          comparison_readiness: { status: 'partial' },
        },
      };
      return {
        policies: [mockCompanyPolicyRow()],
        normalized,
        policyReview: mockPolicyReviewPayload({
          entitlement_rows: [{ benefit_key: 'housing', label: 'Housing', max_value: 1200, currency: 'USD' }],
        }),
      };
    }

    default:
      return { policies: [], normalized: null, policyReview: null };
  }
}

export type MockReviewOptions = {
  document_title?: string;
  entitlement_rows?: Array<Record<string, unknown>>;
  issues?: Array<{ message: string; tier?: string }>;
  employee_visibility?: Record<string, unknown>;
  readiness?: Record<string, unknown>;
};

/** Policy review aggregate (GET /api/hr/policy-review). */
export function mockPolicyReviewPayload(options: MockReviewOptions = {}): Record<string, unknown> {
  const {
    document_title = 'Company policy.pdf',
    entitlement_rows = [],
    issues = [{ message: 'Clarify school search cap for dual assignments.', tier: 'publish' }],
    employee_visibility = { employee_sees_published_policy_matrix: false },
    readiness = {
      comparison_readiness: { status: 'blocked' },
      comparison_rule_readiness: { comparison_ready_strict: false },
    },
  } = options;

  const entitlement_effective_preview = entitlement_rows.map((row, i) => ({
    benefit_rule_id: `rule-${i}`,
    benefit_key: row.benefit_key || 'generic',
    label: row.label,
    baseline: { max_value: row.max_value, currency: row.currency },
    hr_override: null,
    effective: { max_value: row.max_value, currency: row.currency },
  }));

  return {
    document_title,
    document_type: 'assignment_policy',
    issues,
    employee_visibility,
    readiness,
    entitlement_effective_preview,
    draft_rule_candidates: [],
    schema_version: 2,
    grouped_review: {
      template_domains: {},
      domain_order: [],
      import_summary: {},
      duplicate_merge_summary: {},
      counts: {},
      items_needing_review: { grouped_rows: 0, template_fields: 0 },
      empty_template_slots_by_domain: {},
    },
  };
}

/** Employee assignment package policy (GET /api/employee/me/assignment-package-policy). */
export function mockEmployeePackage(
  kind:
    | 'no_assignment'
    | 'no_policy_found'
    | 'found_under_review'
    | 'found_partial'
    | 'found_full'
    | 'error',
  overrides: Partial<AssignmentPackagePolicyPayload> = {}
): AssignmentPackagePolicyPayload {
  const baseFound = {
    status: 'found' as const,
    ok: true,
    assignment_id: 'asg-1',
    has_policy: true,
    policy: { id: 'pol-1', title: 'Acme Relocation Policy', version: 1, effective_date: '2025-01-01', company_name: 'Acme' },
    benefits: [] as unknown[],
    exclusions: [] as unknown[],
    resolution_context: { assignment_type: 'long_term_assignment' },
    comparison_readiness: {
      comparison_ready: false,
      comparison_blockers: [] as string[],
      partial_numeric_coverage: false,
    },
  };

  switch (kind) {
    case 'no_assignment':
      return { status: 'no_assignment', assignment_id: null, ...overrides } as AssignmentPackagePolicyPayload;
    case 'no_policy_found':
      return {
        status: 'no_policy_found',
        ok: true,
        assignment_id: 'asg-1',
        has_policy: false,
        policy: null,
        benefits: [],
        exclusions: [],
        message: 'HR has not published a policy for your assignment in ReloPass yet.',
        ...overrides,
      } as AssignmentPackagePolicyPayload;
    case 'found_under_review':
      return {
        ...baseFound,
        comparison_available: false,
        comparison_readiness: { comparison_ready: false, comparison_blockers: ['missing_limits'], partial_numeric_coverage: false },
        benefits: [],
        ...overrides,
      } as AssignmentPackagePolicyPayload;
    case 'found_partial':
      return {
        ...baseFound,
        comparison_available: false,
        comparison_readiness: { comparison_ready: false, comparison_blockers: [], partial_numeric_coverage: true },
        benefits: [
          {
            benefit_key: 'temporary_housing',
            included: true,
            max_value: 3000,
            currency: 'USD',
            approval_required: false,
          },
        ],
        ...overrides,
      } as AssignmentPackagePolicyPayload;
    case 'found_full':
      return {
        ...baseFound,
        comparison_available: true,
        comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
        benefits: [
          {
            benefit_key: 'temporary_housing',
            included: true,
            max_value: 3000,
            currency: 'USD',
            approval_required: true,
          },
        ],
        ...overrides,
      } as AssignmentPackagePolicyPayload;
    case 'error':
      return {
        status: 'error',
        ok: false,
        assignment_id: null,
        has_policy: false,
        policy: null,
        benefits: [],
        exclusions: [],
        message: 'Service unavailable',
        ...overrides,
      } as AssignmentPackagePolicyPayload;
    default:
      return baseFound as AssignmentPackagePolicyPayload;
  }
}

/** Resolve workspace + lifecycle + employee compare bundle for layout tests. */
export function resolveLayoutModelFromState(type: MockPolicyStateType): {
  resolved: HrPolicyWorkspaceResolved;
  lifecycle: HrPolicyLifecycleContext;
  employeePreviewCompare: NonNullable<HrPolicyWorkspaceLayoutProps['employeePreviewCompare']> | null;
  entitlementPreview: Array<Record<string, unknown>>;
} {
  const { policies, normalized, policyReview } = mockPolicyState(type);
  const resolved = resolveHrPolicyWorkspaceState({ policies, normalized, policyReview });
  const lifecycle = deriveHrPolicyLifecycleContext(normalized, resolved);
  const rawPreview = policyReview?.entitlement_effective_preview;
  const entitlementPreview = Array.isArray(rawPreview) ? (rawPreview as Array<Record<string, unknown>>) : [];
  if (resolved.phase === 'no_policy') {
    return { resolved, lifecycle, employeePreviewCompare: null, entitlementPreview };
  }
  const publishedComparison = derivePublishedComparisonSummary(normalized);
  const workingComparison = deriveWorkingVersionComparisonSummary(normalized);
  const employeePreviewCompare = buildEmployeePreviewCompare({
    resolved,
    draftEntitlementPreview: entitlementPreview,
    publishedComparison,
    workingComparison,
  });
  return { resolved, lifecycle, employeePreviewCompare, entitlementPreview };
}

export function renderHrPolicyLayout(
  model: ReturnType<typeof resolveLayoutModelFromState>,
  props: Partial<HrPolicyWorkspaceLayoutProps> = {}
) {
  const noop = () => {};
  return React.createElement(HrPolicyWorkspaceLayout, {
    resolved: model.resolved,
    lifecycle: model.lifecycle,
    documentsCount: 0,
    loading: false,
    reviewUnavailable: false,
    starterTemplateBusy: null,
    starterError: null,
    onSelectStarterTemplate: noop,
    onUploadDocument: noop,
    onReviewDraft: noop,
    onReviewDraftReplacement: noop,
    onScrollToStarterBaselines: noop,
    onAdjustBenefits: noop,
    onRequestPublishPreflight: noop,
    publishBusy: false,
    publishDataReady: true,
    employeePreviewCompare: model.employeePreviewCompare,
    ...props,
  });
}
