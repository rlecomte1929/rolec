import React from 'react';

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

interface DateSeparatorProps {
  date: string;
}

export const DateSeparator: React.FC<DateSeparatorProps> = ({ date }) => (
  <div className="flex items-center gap-4 py-4" role="separator" aria-label={`Messages from ${formatDate(date)}`}>
    <div className="flex-1 h-px bg-[#e2e8f0]" aria-hidden />
    <span
      className="text-xs uppercase tracking-wider text-[#94a3b8] flex-shrink-0"
      style={{ fontSize: '11px', letterSpacing: '0.05em' }}
    >
      {formatDate(date)}
    </span>
    <div className="flex-1 h-px bg-[#e2e8f0]" aria-hidden />
  </div>
);
