/**
 * ReloPass typed analytics events (client-side UX events).
 *
 * Thin, typed wrappers over `track()` from ./analytics so event names are
 * consistent (snake_case, no typos) and property shapes are enforced at compile
 * time. Server-authoritative events (case_created, policy_published, exception
 * requests) are captured in the Python backend via posthog_client.py, not here.
 *
 * PII contract — NEVER include: names, emails, passport numbers, exact salary,
 * dates of birth. Safe: ids, enums, counts, booleans, city names, durations,
 * amounts in EUR. (initAnalytics also strips known PII keys as a backstop.)
 */

import { track } from './analytics';

// ─── Shared type unions ──────────────────────────────────────────────────────

export type WizardStepName =
  | 'move_details'
  | 'about_you'
  | 'my_people'
  | 'work_and_place'
  | 'review';

export type ServiceCategory =
  | 'movers'
  | 'schools'
  | 'housing'
  | 'banking'
  | 'language_training'
  | 'tax_equalization'
  | 'other';

export type CasePhase =
  | 'pre_departure'
  | 'immigration'
  | 'logistics'
  | 'arrival'
  | 'post_arrival'
  | 'repatriation';

// ─── Wizard funnel ───────────────────────────────────────────────────────────

/** Fired when an employee advances past a completed intake-wizard step. */
export function trackWizardStepCompleted(props: {
  case_id: string;
  step_number: number; // 1-indexed
  step_name: WizardStepName;
  duration_seconds: number;
}): void {
  track('wizard_step_completed', props);
}

/** Fired when the employee submits the full intake wizard. */
export function trackWizardCompleted(props: {
  case_id: string;
  total_duration_seconds: number;
  has_family: boolean;
  has_spouse_wants_to_work: boolean;
}): void {
  track('wizard_completed', props);
}

// ─── Estimate review ─────────────────────────────────────────────────────────

/**
 * Fired once when the Estimate Review breakdown finishes loading. The headline
 * signal for cost-vs-policy health across cases.
 */
export function trackEstimateReviewOpened(props: {
  case_id: string;
  any_line_over_policy: boolean;
  lines_over_policy_count: number;
  lines_within_policy_count: number;
  lines_no_cap_count: number;
  personal_cost_eur: number;
  total_package_eur: number;
  policy_budget_eur: number;
}): void {
  track('estimate_review_opened', props);
}

/** Fired when the estimate review leads to an action. */
export function trackEstimateReviewAction(props: {
  case_id: string;
  action: 'edit_selection' | 'request_exception' | 'proceed_with_personal_cost' | 'submit_within_policy';
  personal_cost_eur: number;
  any_line_over_policy: boolean;
}): void {
  track('estimate_review_action', props);
}

// ─── Supporting events ───────────────────────────────────────────────────────

/** Fired when an employee completes a task in the plan view. */
export function trackPlanTaskCompleted(props: {
  case_id: string;
  task_id: string;
  phase: CasePhase;
  is_overdue: boolean;
}): void {
  track('plan_task_completed', props);
}

/** Fired when an employee selects a vendor from recommendations. */
export function trackVendorSelected(props: {
  case_id: string;
  vendor_id: string;
  vendor_category: ServiceCategory;
  is_within_policy: boolean;
  recommendation_rank: number; // 1-indexed position when selected
}): void {
  track('vendor_selected', props);
}
