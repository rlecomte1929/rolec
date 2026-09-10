/**
 * Relocation plan CTA → in-app routes (reuses existing ROUTE_DEFS / employee patterns).
 * Backend sends wire types (`upload_document`, `view_details`, …); semantic hints come from labels via `relocationTaskCtaSemantic`.
 */
import { buildRoute } from '../../../navigation/routes';
import { withAssignmentQuery } from '../../../utils/employeeAssignmentScope';
import type { RelocationPlanCtaDTO, RelocationPlanCtaTypeWire } from '../../../types/relocationPlanView';
import type { RelocationPlanCtaNavigateContext, CtaNavigateTarget, RelocationTaskCtaSemantic } from './relocationPlanCtaTypes';
import { relocationTaskCtaSemantic } from './relocationTaskCtaSemantic';

// [AIQ-1547] Employee "do the work" surface for form/requirement tasks reached from
// the roadmap. The roadmap is only shown once intake is submitted, so routing these
// CTAs back to the intake wizard dead-ended on its last step (BUG-260715-A317: "all
// the buttons are linked to the last page of the intake wizard … circular connection
// with limited value"). Dossier & Forms lists the case's forms + destination
// requirements and is where documents get generated — the useful landing the reporter
// expected. An optional formHint focuses that form via the page's ?form=<key> param.
function employeeCaseDossierTarget(ctx: RelocationPlanCtaNavigateContext): CtaNavigateTarget {
  const base = buildRoute('employeeCaseDossier', { caseId: ctx.routeCaseId.trim() });
  // A group hint wins: it means the task's forms are a set, and ?form= could only ever
  // expand one of them. See formGroupHint in relocationPlanCtaTypes.ts.
  const group = (ctx.formGroupHint ?? '').trim();
  if (group) return { kind: 'internal', to: `${base}?forms=${encodeURIComponent(group)}` };
  const hint = (ctx.formHint ?? '').trim();
  return { kind: 'internal', to: hint ? `${base}?form=${encodeURIComponent(hint)}` : base };
}

// There is no `/employee/case/:id/summary` route — this silently fell through React
// Router's catch-all to the dashboard. Route employee "review/overview" CTAs (and the
// untyped fallback) to the roadmap (the case's overview page) via buildRoute, so a bad
// route key is a compile error, not a dead link the literal-only navigate guard can't see.
function employeeCaseOverview(routeCaseId: string): string {
  return buildRoute('employeeCaseRoadmap', { caseId: routeCaseId.trim() });
}

/** Employee messages deep-link (see Messages.tsx — uses `assignmentId`, not `assignment`). */
function employeeMessagesForCase(routeCaseId: string): string {
  const base = buildRoute('messages');
  return `${base}?assignmentId=${encodeURIComponent(routeCaseId)}`;
}

function resolveOpenInternalRouteEmployee(ctx: RelocationPlanCtaNavigateContext, cta: RelocationPlanCtaDTO): CtaNavigateTarget {
  const label = (cta.label || '').toLowerCase();
  const aid = ctx.routeCaseId.trim();
  const resCase = (ctx.resourceCaseId ?? ctx.routeCaseId).trim() || ctx.routeCaseId;

  if (label.includes('quote')) {
    return {
      kind: 'internal',
      to: withAssignmentQuery(buildRoute('quotesInbox'), aid),
    };
  }
  if (label.includes('resource')) {
    // Case-scoped resources when we have a backend case id; else global resources with assignment scope.
    return {
      kind: 'internal',
      to: buildRoute('caseResources', { caseId: resCase }),
    };
  }
  return {
    kind: 'internal',
    to: withAssignmentQuery(buildRoute('resources'), aid),
  };
}

function resolveOpenInternalRouteHr(ctx: RelocationPlanCtaNavigateContext, cta: RelocationPlanCtaDTO): CtaNavigateTarget {
  const label = (cta.label || '').toLowerCase();
  const aid = ctx.routeCaseId.trim();

  if (label.includes('quote')) {
    // TODO(relopass): HR-scoped quotes hub if distinct from employee inbox; until then use services entry.
    return {
      kind: 'internal',
      to: aid ? withAssignmentQuery(buildRoute('services'), aid) : buildRoute('services'),
    };
  }
  if (label.includes('resource')) {
    const resCase = (ctx.resourceCaseId ?? ctx.routeCaseId).trim() || ctx.routeCaseId;
    return { kind: 'internal', to: buildRoute('caseResources', { caseId: resCase }) };
  }
  return { kind: 'internal', to: buildRoute('hrResources') };
}

function viewDetailsTargetForRole(ctx: RelocationPlanCtaNavigateContext, sem: RelocationTaskCtaSemantic): CtaNavigateTarget {
  const aid = ctx.routeCaseId.trim();

  if (ctx.role === 'hr') {
    if (sem === 'view_requirements') {
      // TODO(relopass): confirm compliance route param is always assignment id; add caseId variant if API differs.
      return { kind: 'internal', to: buildRoute('hrCompliance', { id: aid }) };
    }
    // review_case & default: assignment review surface
    return { kind: 'internal', to: buildRoute('hrAssignmentReview', { id: aid }) };
  }

  if (sem === 'view_requirements') {
    // [AIQ-1547] Requirements land on Dossier & Forms (forms + destination requirements),
    // not the completed intake wizard's last step.
    return employeeCaseDossierTarget(ctx);
  }

  // Employee "review_case" → intake summary (no separate employee case review route).
  return { kind: 'internal', to: employeeCaseOverview(aid) };
}

function uploadDocumentTarget(ctx: RelocationPlanCtaNavigateContext): CtaNavigateTarget {
  const aid = ctx.routeCaseId.trim();

  if (ctx.role === 'hr') {
    // TODO(relopass): deep-link submission center to `assignmentId` / `caseId` when that page is implemented.
    return { kind: 'internal', to: buildRoute('submissionCenter') };
  }

  // [doc-flow P3] Document-upload tasks land on the case-scoped documents surface —
  // the dedicated page that hosts case-document uploads. ?doc=<docKey> focuses that
  // document's upload control; completing the upload marks the document present, which
  // the relocation-plan view re-derives to a completed task on its next fetch.
  const base = buildRoute('employeeCaseDocuments', { caseId: aid });
  const hint = (ctx.formHint ?? '').trim();
  return { kind: 'internal', to: hint ? `${base}?doc=${encodeURIComponent(hint)}` : base };
}

function completeWizardStepTarget(ctx: RelocationPlanCtaNavigateContext): CtaNavigateTarget {
  const aid = ctx.routeCaseId.trim();

  if (ctx.role === 'hr') {
    // HR drives intake via case summary + assignment review — same assignment id as plan API.
    return { kind: 'internal', to: buildRoute('hrCaseSummary', { caseId: aid }) };
  }

  // [AIQ-1547] Employee form/data tasks reached from the roadmap land on Dossier & Forms,
  // not the completed intake wizard (which dead-ended on its last step).
  return employeeCaseDossierTarget(ctx);
}

function contactOrMessagesTarget(ctx: RelocationPlanCtaNavigateContext): CtaNavigateTarget {
  if (ctx.role === 'hr') {
    return { kind: 'internal', to: buildRoute('hrMessages') };
  }
  return { kind: 'internal', to: employeeMessagesForCase(ctx.routeCaseId.trim()) };
}

/**
 * Resolve backend CTA to navigation target (internal path or external URL).
 */
export function resolveRelocationPlanCtaTarget(
  ctx: RelocationPlanCtaNavigateContext,
  cta: RelocationPlanCtaDTO | null | undefined
): CtaNavigateTarget {
  const raw = cta?.target?.trim();
  if (raw) {
    if (/^https?:\/\//i.test(raw)) {
      return { kind: 'external', href: raw };
    }
    return { kind: 'internal', to: raw.startsWith('/') ? raw : `/${raw}` };
  }

  const fallbackEmployee = employeeCaseOverview(ctx.routeCaseId.trim());
  const fallbackHr = buildRoute('hrCaseSummary', { caseId: ctx.routeCaseId.trim() });
  const fallbackSummary = ctx.role === 'hr' ? fallbackHr : fallbackEmployee;

  const sem = relocationTaskCtaSemantic(cta);

  switch (cta?.type as RelocationPlanCtaTypeWire | undefined) {
    case 'upload_document':
      return uploadDocumentTarget(ctx);
    case 'complete_wizard_step':
      return completeWizardStepTarget(ctx);
    case 'view_details':
      return viewDetailsTargetForRole(ctx, sem);
    case 'contact_hr':
    case 'open_messages':
      return contactOrMessagesTarget(ctx);
    case 'open_internal_route':
      if (!cta) return { kind: 'internal', to: fallbackSummary };
      return ctx.role === 'hr'
        ? resolveOpenInternalRouteHr(ctx, cta)
        : resolveOpenInternalRouteEmployee(ctx, cta);
    case 'open_external_url':
      return { kind: 'internal', to: fallbackSummary };
    case 'none':
    default:
      return { kind: 'internal', to: fallbackSummary };
  }
}
