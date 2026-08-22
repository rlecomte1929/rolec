export type CtaNavigateTarget = { kind: 'internal'; to: string } | { kind: 'external'; href: string };

export type RelocationPlanCtaNavigateContext = {
  routeCaseId: string;
  resourceCaseId?: string | null;
  role?: 'employee' | 'hr';
  /** [AIQ-1252] Best-effort dossier deep-link key (a document-upload task's doc key);
   *  appended as ?form= so the dossier can auto-expand the matching form. */
  formHint?: string | null;
  /**
   * Comma-separated tokens for a task whose forms are a GROUP rather than one form;
   * appended as ?forms= so the dossier scopes its list to every match.
   *
   * "Confirm family / dependent details" is the case this exists for. It carries
   * `required_inputs=()` (relocation_plan_task_library.py:112), so there is no key to
   * use as a formHint — and its forms are corridor-specific spouse/child pairs
   * (FAM-SPOUSE + FAM-CHILD, or DEP-PARTNER + DEP-CHILD, AE-FAM-*, ES-FAM-*, JP-DEP-*).
   * A single ?form= resolves through `forms.find(...)`, so it would expand whichever
   * one happened to sort first and hide the other. ?forms= shows the set.
   */
  formGroupHint?: string | null;
};

export type RelocationTaskCtaSemantic =
  | 'upload_document'
  | 'open_form'
  | 'review_case'
  | 'view_requirements'
  | 'contact_hr'
  | 'open_quotes'
  | 'open_resources';
