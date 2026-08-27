/**
 * Navigation ribbon for Services flow - allows users to jump between sections.
 */
import React from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { buildRoute, type RouteKey } from '../../navigation/routes';
import { isRfqEnabled } from '../../featureFlags';

// [AIQ-1285] case-scoped step routes; `match` is the path tail used for active state.
const ALL_STEPS = [
  { key: 'services', routeKey: 'caseServices' as RouteKey, match: '/services/select', label: 'Select services' },
  { key: 'questions', routeKey: 'caseServicesQuestions' as RouteKey, match: '/services/questions', label: 'Preferences' },
  { key: 'recommendations', routeKey: 'caseServicesRecommendations' as RouteKey, match: '/services/recommendations', label: 'Recommendations' },
  { key: 'estimate', routeKey: 'caseServicesEstimate' as RouteKey, match: '/services/estimate', label: 'Review & budget' },
  { key: 'rfq', routeKey: 'caseServicesRfqNew' as RouteKey, match: '/services/rfq/new', label: 'Request quotes' },
] as const;

export const ServicesNavRibbon: React.FC = () => {
  const location = useLocation();
  const { caseId } = useParams<{ caseId?: string }>();
  const currentPath = location.pathname;
  const STEPS = isRfqEnabled() ? ALL_STEPS : ALL_STEPS.filter((s) => s.key !== 'rfq');

  // Ribbon only navigates within the case-scoped flow; without a caseId there's
  // nothing to link to (the legacy redirect handles entry from path-less URLs).
  if (!caseId) return null;

  return (
    <nav
      className="flex flex-wrap items-center gap-1 p-2 rounded-lg bg-[#f8fafc] border border-[#e2e8f0] mb-6 overflow-x-auto"
      aria-label="Services flow navigation"
    >
      {STEPS.map((step, idx) => {
        const isActive = currentPath.endsWith(step.match);
        const path = buildRoute(step.routeKey, { caseId });

        return (
          <React.Fragment key={step.key}>
            {idx > 0 && (
              <span className="text-slate-500 text-xs mx-1" aria-hidden>
                ›
              </span>
            )}
            <Link
              to={path}
              className={`px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors ${
                isActive
                  ? 'bg-[#0b2b43] text-white'
                  : 'text-[#4b5563] hover:bg-[#e2e8f0] hover:text-[#0b2b43]'
              }`}
            >
              {step.label}
            </Link>
          </React.Fragment>
        );
      })}
    </nav>
  );
};
