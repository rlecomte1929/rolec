import React from 'react';

export interface SegmentedOption {
  value: string;
  label: string;
  description?: string;
  icon?: React.ReactNode;
}

interface SegmentedOptionCardsProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export const SegmentedOptionCards: React.FC<SegmentedOptionCardsProps> = ({ options, value, onChange, className = '' }) => (
  <div
    className={`grid gap-3 ${className}`}
    style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
  >
    {options.map((o) => {
      const selected = o.value === value;
      return (
        <button
          key={o.value}
          type="button"
          aria-pressed={selected}
          onClick={() => onChange(o.value)}
          className={`relative flex flex-col items-start rounded-xl px-4 py-4 text-left transition ${
            selected
              ? 'border-2 border-navy-800 bg-navy-50 shadow-sm'
              : 'border border-[#e2e8f0] bg-white hover:border-navy-600 hover:bg-navy-50'
          }`}
        >
          {selected && (
            <span className="absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-full bg-accent-500 text-white" aria-hidden="true">✓</span>
          )}
          {o.icon && <span className="mb-2 text-navy-700">{o.icon}</span>}
          <span className="text-[14px] font-semibold text-navy-800">{o.label}</span>
          {o.description && <span className="mt-0.5 text-[12px] text-[#6b7280]">{o.description}</span>}
        </button>
      );
    })}
  </div>
);
