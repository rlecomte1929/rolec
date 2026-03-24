import React from 'react';
import { Link } from 'react-router-dom';
import { ROUTE_DEFS } from '../../navigation/routes';

const backLinkClass =
  'inline-flex font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#0b2b43] border-2 border-[#0b2b43] text-[#0b2b43] hover:bg-[#e6f2f4] px-3 py-2 text-sm min-h-[44px] items-center';

export interface RelocationPlanPageHeaderProps {
  backToSummaryHref: string;
}

export const RelocationPlanPageHeader: React.FC<RelocationPlanPageHeaderProps> = ({
  backToSummaryHref,
}) => {
  return (
    <header className="mb-6 space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-[#0b2b43] tracking-tight">Relocation plan</h1>
          <p className="text-sm text-[#4b5563] mt-1 max-w-2xl">
            Your move as a simple roadmap: the card below is what to do next (and why). Work through the active phase;
            open a task only when you want the full steps.
          </p>
          <p className="text-xs text-[#64748b] mt-2">
            <span className="text-[#6b7280]">Informational guidance only.</span>{' '}
            <Link to={ROUTE_DEFS.trust.path} className="text-[#0b2b43] underline underline-offset-2 hover:text-[#123651]">
              How we handle your information
            </Link>
          </p>
        </div>
        <Link to={backToSummaryHref} className={`${backLinkClass} shrink-0 self-start`}>
          ← Back to My case
        </Link>
      </div>
    </header>
  );
}
