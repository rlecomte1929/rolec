import React from 'react';
import type { ServiceItem } from './serviceConfig';

interface ServiceCardProps {
  item: ServiceItem;
  selected: boolean;
  onToggle: () => void;
}

export const ServiceCard: React.FC<ServiceCardProps> = ({ item, selected, onToggle }) => {
  const disabled = !item.enabled;

  return (
    <div
      role="checkbox"
      aria-checked={selected}
      aria-disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onClick={disabled ? undefined : onToggle}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          onToggle();
        }
      }}
      className={`
        flex items-center gap-3 py-3 px-4 rounded-lg border transition-all duration-150
        ${disabled
          ? 'opacity-60 cursor-not-allowed border-[#e2e8f0] bg-[#f8fafc]'
          : selected
            ? 'border-[#0b2b43] bg-[#eef4f8]/50 cursor-pointer shadow-sm'
            : 'border-[#e2e8f0] bg-white hover:border-[#94a3b8] hover:shadow-sm cursor-pointer'
        }
      `}
    >
      <div className="shrink-0 w-9 h-9 rounded-lg bg-[#f1f5f9] flex items-center justify-center text-lg">
        {item.icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-[#0b2b43]">{item.title}</span>
          {disabled && (
            <span className="shrink-0 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide rounded-full bg-[#e2e8f0] text-[#6b7280]">
              Coming soon
            </span>
          )}
        </div>
        <p className="text-sm text-[#6b7280] mt-0.5 line-clamp-2">{item.description}</p>
      </div>
      <div className="shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center">
        {selected ? (
          <div className="w-6 h-6 rounded-full bg-[#0b2b43] flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          </div>
        ) : (
          <div className="w-6 h-6 rounded-full border-2 border-[#d1d5db]" />
        )}
      </div>
    </div>
  );
};
