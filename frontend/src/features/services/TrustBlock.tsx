import React from 'react';

export const TrustBlock: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`flex items-center gap-4 p-5 rounded-xl border border-[#e2e8f0] bg-white shadow-sm ${className}`}>
    <div className="shrink-0 w-12 h-12 rounded-full bg-[#eef4f8] flex items-center justify-center">
      <svg className="w-6 h-6 text-[#0b2b43]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    </div>
    <ul className="flex flex-wrap gap-6 text-sm text-[#4b5563]">
      <li className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-[#0b2b43]" aria-hidden />
        Guided steps
      </li>
      <li className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-[#0b2b43]" aria-hidden />
        Curated options
      </li>
      <li className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-[#0b2b43]" aria-hidden />
        Private by design
      </li>
    </ul>
  </div>
);
