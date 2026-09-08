import React from 'react';

interface AutosaveChipProps {
  state: 'saved' | 'saving' | 'error';
  className?: string;
}

const CONTENT: Record<AutosaveChipProps['state'], { text: string; cls: string }> = {
  saved:  { text: 'Draft saved', cls: 'border-accent-500/25 bg-accent-50 text-accent-600' },
  saving: { text: 'Saving…',     cls: 'border-[#e2e8f0] bg-[#f3f4f6] text-[#6b7280]' },
  error:  { text: "Couldn't save — retrying", cls: 'border-[#e6c9c9] bg-[#f7eeee] text-[#7a2a2a]' },
};

export const AutosaveChip: React.FC<AutosaveChipProps> = ({ state, className = '' }) => {
  const { text, cls } = CONTENT[state];
  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-semibold ${cls} ${className}`}
    >
      {state === 'saved' && <span aria-hidden="true">✓</span>}
      {text}
    </span>
  );
};
