import React from 'react';

interface PlatformPreviewProps {
  highlights: readonly string[];
  cta: React.ReactNode;
  className?: string;
}

export const PlatformPreview: React.FC<PlatformPreviewProps> = ({
  highlights,
  cta,
  className = '',
}) => {
  return (
    <div
      className={`rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8 ${className}`}
    >
      <div className="flex flex-wrap gap-2 mb-6">
        {highlights.map((label) => (
          <span
            key={label}
            className="inline-flex items-center rounded-full border border-marketing-border bg-marketing-surface-muted px-3 py-1 text-xs font-medium text-marketing-text-muted"
          >
            {label}
          </span>
        ))}
      </div>
      <div>{cta}</div>
    </div>
  );
};
