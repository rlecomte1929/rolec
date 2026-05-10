export type CtaNavigateTarget = { kind: 'internal'; to: string } | { kind: 'external'; href: string };

export type RelocationPlanCtaNavigateContext = {
  routeCaseId: string;
  resourceCaseId?: string | null;
  role?: 'employee' | 'hr';
};

export type RelocationTaskCtaSemantic =
  | 'upload_document'
  | 'open_form'
  | 'review_case'
  | 'view_requirements'
  | 'contact_hr'
  | 'open_quotes'
  | 'open_resources';
