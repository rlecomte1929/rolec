/**
 * Relocation plan CTA → in-app routes (reuses existing ROUTE_DEFS / employee patterns).
 * Backend sends wire types (`upload_document`, `view_details`, …); semantic hints come from labels via `relocationTaskCtaSemantic`.
 */
import { buildRoute } from '../../../navigation/routes';
import { withAssignmentQuery } from '../../../utils/employeeAssignmentScope';
import type { RelocationPlanCtaDTO, RelocationPlanCtaTypeWire } from '../../../types/relocationPlanView';
import type { RelocationPlanCtaNavigateContext, CtaNavigateTarget, RelocationTaskCtaSemantic } from './relocationPlanCtaTypes';
import { relocationTaskCtaSemantic } from './relocationTaskCtaSemantic';

function employeeCaseWizardStep(routeCaseId: string, step: number): string {
  return `/employee/case/${encodeURIComponent(routeCaseId)}/wizard/${step}`;
}

function employeeCaseSummary(routeCaseId: string): string {
  return `/employee/case/${encodeURIComponent(routeCaseId)}/summary`;
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
    // Requirements list lives in wizard step 5 today.
    // TODO(relopass): dedicated employee requirements/compliance page when available.
    return { kind: 'internal', to: employeeCaseWizardStep(aid, 5) };
  }

  // Employee "review_case" → intake summary (no separate employee case review route).
  return { kind: 'internal', to: employeeCaseSummary(aid) };
}

function uploadDocumentTarget(ctx: RelocationPlanCtaNavigateContext): CtaNavigateTarget {
  const aid = ctx.routeCaseId.trim();

  if (ctx.role === 'hr') {
    // TODO(relopass): deep-link submission center to `assignmentId` / `caseId` when that page is implemented.
    return { kind: 'internal', to: buildRoute('submissionCenter') };
  }

  // Passport / document upload UI lives on wizard step 2 today.
  // TODO(relopass): `/employee/case/:id/documents` or summary anchor when a unified upload area exists.
  return { kind: 'internal', to: employeeCaseWizardStep(aid, 2) };
}

function completeWizardStepTarget(ctx: RelocationPlanCtaNavigateContext): CtaNavigateTarget {
  const aid = ctx.routeCaseId.trim();

  if (ctx.role === 'hr') {
    // HR drives intake via case summary + assignment review — same assignment id as plan API.
    return { kind: 'internal', to: buildRoute('hrCaseSummary', { caseId: aid }) };
  }

  // Wizard normalizes to first incomplete step when landing on `/wizard/1`.
  return { kind: 'internal', to: employeeCaseWizardStep(aid, 1) };
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

  const fallbackEmployee = employeeCaseSummary(ctx.routeCaseId.trim());
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
