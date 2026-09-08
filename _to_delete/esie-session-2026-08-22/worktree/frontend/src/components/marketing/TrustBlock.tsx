import React from 'react';
import { BulletBlock } from './BulletBlock';

interface TrustBlockProps {
  title: string;
  points: readonly string[];
  className?: string;
}

/**
 * Titled block with bullet points for trust/methodology content.
 */
export const TrustBlock: React.FC<TrustBlockProps> = ({
  title,
  points,
  className = '',
}) => {
  return (
    <div className={className}>
      <h3 className="text-sm font-semibold uppercase tracking-wider text-marketing-accent mb-3">
        {title}
      </h3>
      <BulletBlock items={points} />
    </div>
  );
};
