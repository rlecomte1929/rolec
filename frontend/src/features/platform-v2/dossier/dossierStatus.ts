/**
 * [AIQ-1250] Shared dossier form status helpers.
 *
 * A form whose backend status is `auto_filled` but has every field filled is not
 * really "action needed". These helpers derive the *effective* readiness so the
 * card badge (CaseFormCard) and the page filter chips / summary count
 * (EmployeeDossierPage) agree on what counts as "ready to submit".
 *
 * Note: the dossier list data exposes which docs are *required*
 * (`template.required_documents`) but not which are *uploaded* (those are
 * lazy-fetched per form), so "no required docs" is the proxy for ready.
 */
import type { CaseFormSummary } from '../../../api/dossier';

/** UI-only "blocked" state: a blocker form set and not yet terminal. */
export function isUiBlocked(form: CaseFormSummary): boolean {
  return (
    !!form.blocker_form_id &&
    form.status !== 'submitted' &&
    form.status !== 'approved' &&
    form.status !== 'rejected'
  );
}

/** True when every field has a value (matches the displayed "100% filled"). */
export function allFieldsFilled(form: CaseFormSummary): boolean {
  const total = form.fields_summary.total;
  const filled = form.fields_summary.filled_by_ai + form.fields_summary.filled_by_human;
  return total > 0 && filled >= total;
}

/** True when the form's template lists any required supporting documents. */
export function requiresDocuments(form: CaseFormSummary): boolean {
  return (form.template.required_documents?.length ?? 0) > 0;
}

/**
 * A 100%-filled `auto_filled` form with no required supporting docs is ready to
 * submit — not "action needed". (Blocked forms are never "ready".)
 */
export function isEffectivelyReady(form: CaseFormSummary): boolean {
  return (
    !isUiBlocked(form) &&
    form.status === 'auto_filled' &&
    allFieldsFilled(form) &&
    !requiresDocuments(form)
  );
}
