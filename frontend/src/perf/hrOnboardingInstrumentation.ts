/**
 * HR first-session onboarding instrumentation (AIQ-1223b).
 *
 * Canonical event names for the first actions an HR admin takes in a brand-new
 * workspace. These are the behavioural signals the inference-based onboarding
 * (AIQ-1223) reads to auto-configure the workspace instead of asking upfront —
 * see `docs/design/aiq-1223-inference-onboarding-spec.md`.
 *
 * Events are fired via `track()` (`frontend/src/analytics.ts`), which is a no-op
 * unless `VITE_POSTHOG_KEY` is set. Mirrors the constants-module pattern of
 * `assignmentLinkingInstrumentation.ts` (`ASSIGNMENT_FLOW_EVENTS`).
 *
 * PRIVACY: event properties MUST be PII-free. Use ids, counts, booleans, and
 * enum values only — never names, emails, addresses, or free text. The helpers
 * below only accept the typed property shapes declared here.
 */

import { track } from '../analytics';

export const HR_ONBOARDING_EVENTS = {
  /** HR saved their own company profile (reveals company size_band). */
  companyProfileSaved: 'hr_onboarding.company_profile_saved',
  /** HR opened the Policy Builder tab (intent to define policy tiers). */
  policyBuilderOpened: 'hr_onboarding.policy_builder_opened',
  /** HR published a policy (reveals policy tier count). */
  policyPublished: 'hr_onboarding.policy_published',
  /** HR created their first relocation case (reveals mobility volume start). */
  firstCaseCreated: 'hr_onboarding.first_case_created',
} as const;

/**
 * All prop shapes carry an index signature so they satisfy `track()`'s
 * `Record<string, unknown>` parameter without a cast.
 */

/** Non-PII props: presence flags + the size_band enum (already a coarse band). */
export interface CompanyProfileSavedProps {
  has_size_band: boolean;
  has_default_destination_country: boolean;
  has_default_working_location: boolean;
  /** Coarse, non-identifying band (e.g. "51–200"). */
  size_band?: string;
  [key: string]: unknown;
}

export interface PolicyPublishedProps {
  tier_count: number;
  benefit_row_count: number;
  [key: string]: unknown;
}

export interface FirstCaseCreatedProps {
  /** Number of existing cases before this create (0 → genuinely the first). */
  prior_case_count: number;
  [key: string]: unknown;
}

export function trackCompanyProfileSaved(props: CompanyProfileSavedProps): void {
  track(HR_ONBOARDING_EVENTS.companyProfileSaved, props);
}

export function trackPolicyBuilderOpened(): void {
  track(HR_ONBOARDING_EVENTS.policyBuilderOpened);
}

export function trackPolicyPublished(props: PolicyPublishedProps): void {
  track(HR_ONBOARDING_EVENTS.policyPublished, props);
}

export function trackFirstCaseCreated(props: FirstCaseCreatedProps): void {
  track(HR_ONBOARDING_EVENTS.firstCaseCreated, props);
}
