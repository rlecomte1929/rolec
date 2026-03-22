/**
 * Navigation ribbon for Services flow - allows users to jump between sections.
 */
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { buildRoute } from '../../navigation/routes';

const STEPS = [
  { key: 'services', path: '/services', label: 'Select services' },
  { key: 'questions', path: '/services/questions', label: 'Preferences' },
  { key: 'recommendations', path: '/services/recommendations', label: 'Recommendations' },
  { key: 'estimate', path: '/services/estimate', label: 'Review & budget' },
  { key: 'rfq', path: '/services/rfq/new', label: 'Request quotes' },
] as const;

export const ServicesNavRibbon: React.FC = () => {
  const location = useLocation();
  const currentPath = location.pathname;
  const qs = location.search || '';

  return (
    <nav
      className="flex flex-wrap items-center gap-1 p-2 rounded-lg bg-[#f8fafc] border border-[#e2e8f0] mb-6 overflow-x-auto"
      aria-label="Services flow navigation"
    >
      {STEPS.map((step, idx) => {
        const isActive =
          step.path === currentPath ||
          (step.path !== '/services' && currentPath.startsWith(step.path));
        const isServices = step.key === 'services';
        const path = (isServices ? buildRoute('services') : step.path) + qs;

        return (
          <React.Fragment key={step.key}>
            {idx > 0 && (
              <span className="text-[#94a3b8] text-xs mx-1" aria-hidden>
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
