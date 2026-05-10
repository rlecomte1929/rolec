import React from 'react';

interface BulletBlockProps {
  items: readonly string[];
  className?: string;
}

/**
 * Minimal bullet list for problem/solution blocks.
 */
export const BulletBlock: React.FC<BulletBlockProps> = ({
  items,
  className = '',
}) => {
  return (
    <ul
      className={`space-y-2 ${className}`}
      role="list"
    >
      {items.map((item, i) => (
        <li key={i} className="flex gap-3 items-center">
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full bg-marketing-accent"
            aria-hidden
          />
          <span className="text-marketing-body-lg text-marketing-text-muted leading-relaxed">
            {item}
          </span>
        </li>
      ))}
    </ul>
  );
};
