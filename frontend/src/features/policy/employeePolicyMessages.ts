/** Aligned with backend EMPLOYEE_POLICY_FALLBACK_* (employee HR Policy / package page). */
export const EMPLOYEE_HR_POLICY_WAIT_PRIMARY =
  "Your HR team has not published your company's assignment policy in ReloPass yet.";

export const EMPLOYEE_HR_POLICY_WAIT_SECONDARY =
  'This page will show your package and limits after HR publishes the policy from the HR Policy workspace.';

/** When a policy exists but is not yet in a comparison-ready shape (employee cost comparison / badges). */
export const EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_PRIMARY =
  "Your company policy has not yet been published in a form that supports cost comparison.";

export const EMPLOYEE_POLICY_COMPARISON_UNAVAILABLE_SECONDARY =
  'You can still review service costs, but company coverage and limits are not available yet.';

/** Loading copy — avoid vague spinners on policy pages. */
export const EMPLOYEE_POLICY_LOADING_ASSIGNMENT =
  'Checking your assignment and published company policy…';

/** Shown when policy exists but comparison is off — clarifies “partial” vs broken. */
export const EMPLOYEE_POLICY_PARTIAL_INFO_LABEL =
  'Partial policy information';

export const EMPLOYEE_POLICY_PARTIAL_INFO_DETAIL =
  'Your company has a published policy on file, but detailed benefit cards and cost comparison are not shown until the policy meets comparison requirements. You can still review costs on Services; HR can complete missing rules in the Policy workspace.';

/** When comparison is fully available (resolved + comparison gate passed). */
export const EMPLOYEE_POLICY_COMPARISON_ACTIVE_TITLE = 'Policy comparison is available';

export const EMPLOYEE_POLICY_COMPARISON_ACTIVE_BODY =
  'Benefit summaries below use your published assignment policy. Supported flows can compare selections to policy limits.';
