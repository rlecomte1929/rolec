/**
 * outcome-reason-codes.ts — standardised reason codes for assignment outcomes
 * ─────────────────────────────────────────────────────────────────────────────
 * Used by:
 *   - HR feedback forms when marking a provider task complete or cancelled
 *   - The outcome_recorder.py backend service (stored in hr_feedback field)
 *   - The nightly-aggregation Edge Function (anomaly detection on decline reasons)
 *   - MATCHING-5E supplier scoring algorithm (reason-weighted score adjustment)
 *
 * Naming convention: CATEGORY_SPECIFIC_DETAIL (UPPER_SNAKE_CASE)
 * ─────────────────────────────────────────────────────────────────────────────
 */

// ─── Completion reason codes (status → 'completed') ──────────────────────────

export const COMPLETION_REASONS = {
  // Positive outcomes
  ON_TIME_WITHIN_BUDGET:    "on_time_within_budget",
  EARLY_DELIVERY:           "early_delivery",
  EXCEEDED_EXPECTATIONS:    "exceeded_expectations",

  // Neutral outcomes
  ON_TIME_OVER_BUDGET:      "on_time_over_budget",
  LATE_BUT_SATISFACTORY:    "late_but_satisfactory",

  // Negative outcomes (still completed, but noted)
  QUALITY_BELOW_STANDARD:   "quality_below_standard",
  SIGNIFICANT_DELAY:        "significant_delay",
  BUDGET_OVERRUN:           "budget_overrun",
} as const;

export type CompletionReason = typeof COMPLETION_REASONS[keyof typeof COMPLETION_REASONS];

// ─── Cancellation / decline reason codes ─────────────────────────────────────

export const CANCELLATION_REASONS = {
  // Supplier-side
  SUPPLIER_CAPACITY:        "supplier_capacity",
  SUPPLIER_SCOPE_MISMATCH:  "supplier_scope_mismatch",
  SUPPLIER_PRICING:         "supplier_pricing",
  SUPPLIER_GEOGRAPHY:       "supplier_geography",
  SUPPLIER_UNRESPONSIVE:    "supplier_unresponsive",

  // HR/client-side
  EMPLOYEE_WITHDREW:        "employee_withdrew",
  ASSIGNMENT_CANCELLED:     "assignment_cancelled",
  BUDGET_WITHDRAWN:         "budget_withdrawn",
  DUPLICATE_REQUEST:        "duplicate_request",

  // External
  VISA_DENIED:              "visa_denied",
  DESTINATION_CHANGE:       "destination_change",
  FORCE_MAJEURE:            "force_majeure",
} as const;

export type CancellationReason = typeof CANCELLATION_REASONS[keyof typeof CANCELLATION_REASONS];

// ─── Display labels (for HR UI dropdowns) ────────────────────────────────────

export const COMPLETION_REASON_LABELS: Record<CompletionReason, string> = {
  on_time_within_budget:    "Delivered on time, within budget",
  early_delivery:           "Delivered ahead of schedule",
  exceeded_expectations:    "Exceeded expectations",
  on_time_over_budget:      "On time, but over budget",
  late_but_satisfactory:    "Late delivery, but satisfactory quality",
  quality_below_standard:   "Quality below standard",
  significant_delay:        "Significant delay",
  budget_overrun:           "Budget overrun (>10%)",
};

export const CANCELLATION_REASON_LABELS: Record<CancellationReason, string> = {
  supplier_capacity:        "Supplier at capacity",
  supplier_scope_mismatch:  "Scope mismatch with supplier",
  supplier_pricing:         "Supplier pricing too high",
  supplier_geography:       "Supplier doesn't cover destination",
  supplier_unresponsive:    "Supplier unresponsive",
  employee_withdrew:        "Employee withdrew from relocation",
  assignment_cancelled:     "Assignment cancelled by HR",
  budget_withdrawn:         "Budget withdrawn",
  duplicate_request:        "Duplicate request",
  visa_denied:              "Visa application denied",
  destination_change:       "Destination changed",
  force_majeure:            "Force majeure",
};

// ─── Score impact weights (used by MATCHING-5E scoring algorithm) ─────────────
// Positive weight = boosts supplier score; negative = penalises.
// Applied as additive modifier to avg_overall_score before normalisation.

export const COMPLETION_REASON_SCORE_DELTA: Record<CompletionReason, number> = {
  on_time_within_budget:    0.0,   // baseline, no adjustment
  early_delivery:           +0.3,
  exceeded_expectations:    +0.5,
  on_time_over_budget:      -0.1,
  late_but_satisfactory:    -0.2,
  quality_below_standard:   -0.5,
  significant_delay:        -0.4,
  budget_overrun:           -0.3,
};

export const CANCELLATION_REASON_SCORE_DELTA: Record<CancellationReason, number> = {
  supplier_capacity:        -0.2,  // supplier couldn't handle load
  supplier_scope_mismatch:  -0.1,  // partly matching failure
  supplier_pricing:          0.0,  // neutral — commercial, not quality
  supplier_geography:        0.0,  // neutral — coverage gap, not quality
  supplier_unresponsive:    -0.5,  // strong negative signal
  employee_withdrew:         0.0,  // not supplier's fault
  assignment_cancelled:      0.0,  // not supplier's fault
  budget_withdrawn:          0.0,  // not supplier's fault
  duplicate_request:         0.0,  // not supplier's fault
  visa_denied:               0.0,  // external factor
  destination_change:        0.0,  // external factor
  force_majeure:             0.0,  // external factor
};

// ─── Type guards ──────────────────────────────────────────────────────────────

export function isCompletionReason(value: string): value is CompletionReason {
  return Object.values(COMPLETION_REASONS).includes(value as CompletionReason);
}

export function isCancellationReason(value: string): value is CancellationReason {
  return Object.values(CANCELLATION_REASONS).includes(value as CancellationReason);
}
