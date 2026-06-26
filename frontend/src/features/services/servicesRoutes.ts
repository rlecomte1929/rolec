/**
 * Services flow route helpers (AIQ-1249a).
 *
 * The services flow URL is case-id-native (/employee/case/:caseId/services/...)
 * but the legacy /services/... routes stay alive for back-compat. servicesStepPath
 * builds the right URL for a step depending on what we know:
 *   - caseId known       → case-scoped path
 *   - else assignmentId  → legacy path + ?assignment=<id>
 *   - else               → bare legacy path
 */
import { buildRoute, type RouteKey } from '../../navigation/routes';
import { withAssignmentQuery } from '../../utils/employeeAssignmentScope';

export type ServicesStep =
  | 'services'
  | 'questions'
  | 'recommendations'
  | 'estimate'
  | 'rfqNew'
  | 'conclusion';

const CASE_ROUTE_KEYS: Record<ServicesStep, RouteKey> = {
  services: 'employeeCaseServices',
  questions: 'employeeCaseServicesQuestions',
  recommendations: 'employeeCaseServicesRecommendations',
  estimate: 'employeeCaseServicesEstimate',
  rfqNew: 'employeeCaseServicesRfqNew',
  conclusion: 'employeeCaseServicesConclusion',
};

const LEGACY_ROUTE_KEYS: Record<ServicesStep, RouteKey> = {
  services: 'services',
  questions: 'servicesQuestions',
  recommendations: 'servicesRecommendations',
  estimate: 'servicesEstimate',
  rfqNew: 'servicesRfqNew',
  conclusion: 'servicesConclusion',
};

export function caseServicesRouteKey(step: ServicesStep): RouteKey {
  return CASE_ROUTE_KEYS[step];
}

export function servicesStepPath(
  step: ServicesStep,
  opts: { caseId?: string | null; assignmentId?: string | null } = {},
): string {
  const caseId = (opts.caseId || '').trim();
  if (caseId) return buildRoute(CASE_ROUTE_KEYS[step], { caseId });
  const legacy = buildRoute(LEGACY_ROUTE_KEYS[step]);
  const aid = (opts.assignmentId || '').trim();
  return aid ? withAssignmentQuery(legacy, aid) : legacy;
}
