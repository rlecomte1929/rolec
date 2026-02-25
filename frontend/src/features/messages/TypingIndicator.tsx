import React from 'react';

interface TypingIndicatorProps {
  name: string;
}

export const TypingIndicator: React.FC<TypingIndicatorProps> = ({ name }) => (
  <div
    className="flex items-center gap-2 self-start mb-3 text-sm text-[#6b7280] opacity-80"
    role="status"
    aria-live="polite"
    aria-label={`${name} is typing`}
  >
    <div className="flex gap-1 px-4 py-2 rounded-[20px] rounded-bl-md bg-[#F5F5F5]">
      <span className="w-2 h-2 rounded-full bg-[#94a3b8] animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-2 h-2 rounded-full bg-[#94a3b8] animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-2 h-2 rounded-full bg-[#94a3b8] animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  </div>
);
