/**
 * Navigation ribbon for Services flow - allows users to jump between sections.
 *
 * AIQ-1249c: step links are built via useServicesScope().linkTo so they are
 * case-id-native (/employee/case/:caseId/services/...) when a case is known, and
 * fall back to the legacy /services/... + ?assignment= form otherwise.
 */
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { isRfqEnabled } from '../../featureFlags';
import { useServicesScope } from './useServicesScope';
import type { ServicesStep } from './servicesRoutes';

const ALL_STEPS: Array<{ key: ServicesStep; label: string }> = [
  { key: 'services', label: 'Select services' },
  { key: 'questions', label: 'Preferences' },
  { key: 'recommendations', label: 'Recommendations' },
  { key: 'estimate', label: 'Review & budget' },
  { key: 'rfqNew', label: 'Request quotes' },
];

export const ServicesNavRibbon: React.FC = () => {
  const location = useLocation();
  const currentPath = location.pathname;
  const { linkTo } = useServicesScope();
  const STEPS = isRfqEnabled() ? ALL_STEPS : ALL_STEPS.filter((s) => s.key !== 'rfqNew');

  return (
    <nav
      className="flex flex-wrap items-center gap-1 p-2 rounded-lg bg-[#f8fafc] border border-[#e2e8f0] mb-6 overflow-x-auto"
      aria-label="Services flow navigation"
    >
      {STEPS.map((step, idx) => {
        const to = linkTo(step.key);
        const path = to.split('?')[0];
        const isActive =
          currentPath === path ||
          (step.key !== 'services' && currentPath.startsWith(`${path}/`));

        return (
          <React.Fragment key={step.key}>
            {idx > 0 && (
              <span className="text-[#94a3b8] text-xs mx-1" aria-hidden>
                ›
              </span>
            )}
            <Link
              to={to}
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
