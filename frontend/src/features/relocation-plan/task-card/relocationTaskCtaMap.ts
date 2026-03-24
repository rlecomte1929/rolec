import type { RelocationPlanCtaDTO } from '../../../types/relocationPlanView';
import type { CtaNavigateTarget } from './relocationPlanCtaTypes';
import { relocationTaskCtaSemantic } from './relocationTaskCtaSemantic';

export type { CtaNavigateTarget, RelocationPlanCtaNavigateContext, RelocationTaskCtaSemantic } from './relocationPlanCtaTypes';
export { resolveRelocationPlanCtaTarget as resolveRelocationTaskCtaTarget } from './relocationPlanCtaRouter';
export { relocationTaskCtaSemantic } from './relocationTaskCtaSemantic';

/**
 * Backend `_wire_cta` maps internal library keys to wire `cta.type` + labels:
 *
 * | Semantic (library)   | Wire `type`              | Typical label        |
 * |---------------------|--------------------------|----------------------|
 * | upload_document     | upload_document          | Upload document      |
 * | open_form           | complete_wizard_step     | Continue             |
 * | review_case         | view_details             | Review               |
 * | view_requirements   | view_details             | View requirements    |
 * | contact_hr          | contact_hr               | Contact HR           |
 * | open_quotes         | open_internal_route      | Get quotes           |
 * | open_resources      | open_internal_route      | Open resources       |
 *
 * Concrete paths: see `relocationPlanCtaRouter.ts`.
 */

export function relocationTaskCtaDefaultButtonLabel(
  cta: RelocationPlanCtaDTO | null | undefined,
  target: CtaNavigateTarget
): string {
  const fromServer = cta?.label?.trim();
  if (fromServer) return fromServer;
  if (target.kind === 'external') return 'Open link';
  const sem = relocationTaskCtaSemantic(cta);
  switch (sem) {
    case 'upload_document':
      return 'Upload';
    case 'open_form':
      return 'Continue';
    case 'review_case':
      return 'Review';
    case 'view_requirements':
      return 'View requirements';
    case 'contact_hr':
      return 'Contact HR';
    case 'open_quotes':
      return 'View quotes';
    case 'open_resources':
      return 'Open resources';
    default:
      return 'Continue';
  }
}
