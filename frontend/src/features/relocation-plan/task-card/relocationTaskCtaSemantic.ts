import type { RelocationPlanCtaDTO } from '../../../types/relocationPlanView';
import type { RelocationTaskCtaSemantic } from './relocationPlanCtaTypes';

/** Maps wire enum + label to a semantic bucket for routing and default labels. */
export function relocationTaskCtaSemantic(cta: RelocationPlanCtaDTO | null | undefined): RelocationTaskCtaSemantic {
  if (!cta) return 'review_case';
  const t = cta.type;
  const label = (cta.label || '').toLowerCase();
  switch (t) {
    case 'upload_document':
      return 'upload_document';
    case 'contact_hr':
      return 'contact_hr';
    case 'complete_wizard_step':
      return 'open_form';
    case 'view_details':
      if (label.includes('requirement')) return 'view_requirements';
      return 'review_case';
    case 'open_internal_route':
      if (label.includes('quote')) return 'open_quotes';
      if (label.includes('resource')) return 'open_resources';
      return 'open_resources';
    default:
      return 'review_case';
  }
}
