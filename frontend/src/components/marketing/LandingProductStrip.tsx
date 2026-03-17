import React from 'react';

export interface ProductStripBlock {
  title: string;
  body: string;
}

interface LandingProductStripProps {
  blocks: readonly ProductStripBlock[];
  className?: string;
}

/**
 * Horizontal 3-block strip for landing hero. Concrete operational message.
 * Desktop: horizontal; mobile: stacked. Restrained, no arrows or decoration.
 */
export const LandingProductStrip: React.FC<LandingProductStripProps> = ({
  blocks,
  className = '',
}) => {
  return (
    <div
      className={`w-full max-w-lg rounded-xl border border-marketing-border bg-marketing-surface p-5 sm:p-6 ${className}`}
      aria-hidden
    >
      <div className="flex flex-col sm:flex-row sm:items-stretch gap-4 sm:gap-6">
        {blocks.map((block, i) => (
          <div
            key={block.title}
            className={`flex-1 min-w-0 border-marketing-border ${
              i < blocks.length - 1 ? 'sm:border-r pr-0 sm:pr-6' : ''
            }`}
          >
            <p className="text-xs font-semibold uppercase tracking-wider text-marketing-text-muted">
              {block.title}
            </p>
            <p className="mt-1.5 text-sm text-marketing-primary leading-snug">
              {block.body}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
