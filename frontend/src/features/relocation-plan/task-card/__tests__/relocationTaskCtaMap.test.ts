import { describe, expect, it } from 'vitest';
import { buildRoute } from '../../../../navigation/routes';
import { withAssignmentQuery } from '../../../../utils/employeeAssignmentScope';
import type { RelocationPlanCtaDTO } from '../../../../types/relocationPlanView';
import {
  relocationTaskCtaSemantic,
  resolveRelocationTaskCtaTarget,
  relocationTaskCtaDefaultButtonLabel,
} from '../relocationTaskCtaMap';

const employeeCtx = { routeCaseId: 'assign-1', resourceCaseId: 'case-uuid-2', role: 'employee' as const };

describe('relocationTaskCtaSemantic', () => {
  it('maps complete_wizard_step to open_form', () => {
    expect(
      relocationTaskCtaSemantic({ type: 'complete_wizard_step', label: 'Continue' })
    ).toBe('open_form');
  });

  it('maps view_details label to view_requirements when appropriate', () => {
    expect(
      relocationTaskCtaSemantic({ type: 'view_details', label: 'View requirements' })
    ).toBe('view_requirements');
  });

  it('maps open_internal_route by label for quotes and resources', () => {
    expect(
      relocationTaskCtaSemantic({ type: 'open_internal_route', label: 'Get quotes' })
    ).toBe('open_quotes');
    expect(
      relocationTaskCtaSemantic({ type: 'open_internal_route', label: 'Open resources' })
    ).toBe('open_resources');
  });
});

describe('resolveRelocationTaskCtaTarget', () => {
  it('uses target path when provided', () => {
    const cta: RelocationPlanCtaDTO = {
      type: 'view_details',
      label: 'Go',
      target: '/custom',
    };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: '/custom',
    });
  });

  it('routes upload_document to employee wizard step 2 (document upload)', () => {
    const cta: RelocationPlanCtaDTO = { type: 'upload_document', label: 'Upload' };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: `/employee/case/${encodeURIComponent('assign-1')}/wizard/2`,
    });
  });

  it('routes complete_wizard_step to employee wizard entry', () => {
    const cta: RelocationPlanCtaDTO = { type: 'complete_wizard_step', label: 'Continue' };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: `/employee/case/${encodeURIComponent('assign-1')}/wizard/1`,
    });
  });

  it('routes view_details (review) to employee case summary', () => {
    const cta: RelocationPlanCtaDTO = { type: 'view_details', label: 'Review' };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: `/employee/case/${encodeURIComponent('assign-1')}/summary`,
    });
  });

  it('routes view_details (requirements) to wizard step 5', () => {
    const cta: RelocationPlanCtaDTO = { type: 'view_details', label: 'View requirements' };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: `/employee/case/${encodeURIComponent('assign-1')}/wizard/5`,
    });
  });

  it('routes contact_hr to messages with assignmentId', () => {
    const cta: RelocationPlanCtaDTO = { type: 'contact_hr', label: 'Contact HR' };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: `${buildRoute('messages')}?assignmentId=${encodeURIComponent('assign-1')}`,
    });
  });

  it('routes open_internal_route Get quotes to quotes inbox with assignment scope', () => {
    const cta: RelocationPlanCtaDTO = { type: 'open_internal_route', label: 'Get quotes' };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: withAssignmentQuery(buildRoute('quotesInbox'), 'assign-1'),
    });
  });

  it('routes open_internal_route Open resources to case resources using resourceCaseId', () => {
    const cta: RelocationPlanCtaDTO = { type: 'open_internal_route', label: 'Open resources' };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: buildRoute('caseResources', { caseId: 'case-uuid-2' }),
    });
  });

  it('falls back to resources with assignment scope for ambiguous open_internal_route', () => {
    const cta: RelocationPlanCtaDTO = { type: 'open_internal_route', label: 'Continue' };
    expect(resolveRelocationTaskCtaTarget(employeeCtx, cta)).toEqual({
      kind: 'internal',
      to: withAssignmentQuery(buildRoute('resources'), 'assign-1'),
    });
  });

  it('routes HR upload_document to submission center placeholder', () => {
    const hrCtx = { routeCaseId: 'hr-assign-1', resourceCaseId: 'case-x', role: 'hr' as const };
    const cta: RelocationPlanCtaDTO = { type: 'upload_document', label: 'Upload' };
    expect(resolveRelocationTaskCtaTarget(hrCtx, cta)).toEqual({
      kind: 'internal',
      to: buildRoute('submissionCenter'),
    });
  });

  it('routes HR view_details to assignment review', () => {
    const hrCtx = { routeCaseId: 'hr-assign-1', role: 'hr' as const };
    const cta: RelocationPlanCtaDTO = { type: 'view_details', label: 'Review' };
    expect(resolveRelocationTaskCtaTarget(hrCtx, cta)).toEqual({
      kind: 'internal',
      to: buildRoute('hrAssignmentReview', { id: 'hr-assign-1' }),
    });
  });

  it('routes HR view_requirements to compliance check', () => {
    const hrCtx = { routeCaseId: 'hr-assign-1', role: 'hr' as const };
    const cta: RelocationPlanCtaDTO = { type: 'view_details', label: 'View requirements' };
    expect(resolveRelocationTaskCtaTarget(hrCtx, cta)).toEqual({
      kind: 'internal',
      to: buildRoute('hrCompliance', { id: 'hr-assign-1' }),
    });
  });
});

describe('relocationTaskCtaDefaultButtonLabel', () => {
  it('prefers server label', () => {
    const cta: RelocationPlanCtaDTO = { type: 'upload_document', label: 'Add file' };
    expect(
      relocationTaskCtaDefaultButtonLabel(cta, { kind: 'internal', to: '/x' })
    ).toBe('Add file');
  });
});
