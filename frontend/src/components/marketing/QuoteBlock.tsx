import React from 'react';

interface QuoteBlockProps {
  quote: string;
  attribution?: string;
  role?: string;
  company?: string;
  /** Optional decorative style */
  large?: boolean;
  className?: string;
}

export const QuoteBlock: React.FC<QuoteBlockProps> = ({
  quote,
  attribution,
  role,
  company,
  large = false,
  className = '',
}) => {
  return (
    <blockquote
      className={`rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8 md:p-10 ${className}`}
    >
      <p
        className={`text-marketing-primary ${
          large ? 'text-xl sm:text-2xl' : 'text-lg sm:text-xl'
        } font-medium leading-relaxed`}
      >
        &ldquo;{quote}&rdquo;
      </p>
      {(attribution || role || company) && (
        <footer className="mt-6">
          {attribution && (
            <cite className="not-italic font-semibold text-marketing-primary">
              {attribution}
            </cite>
          )}
          {(role || company) && (
            <p className="text-sm text-marketing-text-muted mt-0.5">
              {[role, company].filter(Boolean).join(', ')}
            </p>
          )}
        </footer>
      )}
    </blockquote>
  );
};
