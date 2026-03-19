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
      className={`w-full max-w-lg rounded-2xl border border-marketing-border bg-marketing-surface shadow-md p-6 sm:p-7 ${className}`}
      aria-hidden
    >
      <div className="flex flex-col sm:flex-row sm:items-stretch gap-5 sm:gap-0">
        {blocks.map((block, i) => (
          <div
            key={block.title}
            className={`flex-1 min-w-0 sm:px-5 first:sm:pl-0 last:sm:pr-0 ${
              i < blocks.length - 1 ? 'sm:border-r border-slate-300 sm:pr-6' : ''
            }`}
          >
            <p className="text-xs font-bold uppercase tracking-widest text-marketing-accent">
              {block.title}
            </p>
            <p className="mt-2 text-sm font-medium text-marketing-primary leading-snug">
              {block.body}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
