import React from 'react';

interface TrustTeaserProps {
  points: readonly string[];
  className?: string;
}

export const TrustTeaser: React.FC<TrustTeaserProps> = ({
  points,
  className = '',
}) => {
  return (
    <ul
      className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 ${className}`}
      role="list"
    >
      {points.map((point, i) => (
<li key={i} className="flex gap-3 items-center">
            <span
              className="h-2 w-2 shrink-0 rounded-full bg-marketing-accent"
              aria-hidden
            />
          <span className="text-sm text-marketing-text-muted leading-relaxed">
            {point}
          </span>
        </li>
      ))}
    </ul>
  );
};
