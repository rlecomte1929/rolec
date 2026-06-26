export type CtaNavigateTarget = { kind: 'internal'; to: string } | { kind: 'external'; href: string };

export type RelocationPlanCtaNavigateContext = {
  routeCaseId: string;
  resourceCaseId?: string | null;
  role?: 'employee' | 'hr';
  /** [AIQ-1252] Best-effort dossier deep-link key (a document-upload task's doc key);
   *  appended as ?form= so the dossier can auto-expand the matching form. */
  formHint?: string | null;
};

export type RelocationTaskCtaSemantic =
  | 'upload_document'
  | 'open_form'
  | 'review_case'
  | 'view_requirements'
  | 'contact_hr'
  | 'open_quotes'
  | 'open_resources';
