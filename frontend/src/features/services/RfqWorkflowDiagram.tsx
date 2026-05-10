import React from 'react';

const STEPS = [
  { n: 1, title: 'Shortlist', detail: 'Pick providers for each service' },
  { n: 2, title: 'Request quotes', detail: 'Ask vendors for formal prices' },
  { n: 3, title: 'Receive offers', detail: 'Get proposed prices back' },
  { n: 4, title: 'Choose', detail: 'Compare and pick what fits' },
] as const;

/**
 * Simple visual workflow for RFQ (Request For Quotation).
 */
export const RfqWorkflowDiagram: React.FC = () => {
  return (
    <div
      className="rounded-xl border border-[#e2e8f0] bg-white p-4 sm:p-6"
      role="region"
      aria-label="How requesting quotations works in four steps"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-[#64748b] mb-4">How it will work</p>
      <ol className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 list-none p-0 m-0">
        {STEPS.map((step) => (
          <li key={step.n} className="flex gap-3 lg:flex-col lg:text-center lg:items-center">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#0b2b43] text-sm font-bold text-white"
              aria-hidden
            >
              {step.n}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[#0b2b43]">{step.title}</p>
              <p className="text-xs text-[#64748b] mt-1 leading-snug">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-5 text-sm text-[#475569] border-t border-[#f1f5f9] pt-4 leading-relaxed">
        <strong className="text-[#0b2b43]">Your end goal:</strong> a list of{' '}
        <strong>proposed prices</strong> from different vendors, so you can compare numbers side by side and choose the
        best option for your move.
      </p>
    </div>
  );
};
