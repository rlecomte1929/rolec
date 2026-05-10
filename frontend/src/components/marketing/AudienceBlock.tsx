import React from 'react';

interface AudienceBlockProps {
  title: string;
  description: string;
  className?: string;
}

export const AudienceBlock: React.FC<AudienceBlockProps> = ({
  title,
  description,
  className = '',
}) => {
  return (
    <div
      className={`rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8 ${className}`}
    >
      <h3 className="text-marketing-h3 font-semibold text-marketing-primary">
        {title}
      </h3>
      <p className="mt-3 text-sm text-marketing-text-muted leading-relaxed">
        {description}
      </p>
    </div>
  );
};
