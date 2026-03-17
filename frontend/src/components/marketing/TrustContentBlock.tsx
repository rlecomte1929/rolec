import React from 'react';
import { BulletBlock } from './BulletBlock';

interface TrustContentBlockProps {
  title: string;
  intro?: string;
  body?: string;
  points?: readonly string[];
  /** Optional line before bullets, e.g. "You can see:" */
  pointsPrefix?: string;
  closing?: string;
  optional?: string;
  /** Mandatory boundary line (e.g. decisions disclaimer) */
  boundary?: string;
  className?: string;
}

/**
 * Trust section block: title, intro, bullet list, closing.
 */
export const TrustContentBlock: React.FC<TrustContentBlockProps> = ({
  title,
  intro,
  body,
  points,
  pointsPrefix,
  closing,
  optional,
  boundary,
  className = '',
}) => {
  const hasIntro = intro ?? body;
  return (
    <div className={className}>
      <h2 className="text-marketing-h1 font-semibold text-marketing-primary tracking-tight">
        {title}
      </h2>
      {hasIntro && (
        <p className="mt-4 text-marketing-body-lg text-marketing-text-muted leading-relaxed">
          {intro ?? body}
        </p>
      )}
      {points && points.length > 0 && (
        <>
          {pointsPrefix && (
            <p className="mt-3 text-marketing-body-lg text-marketing-text-muted leading-relaxed">
              {pointsPrefix}
            </p>
          )}
          <div className={`${pointsPrefix ? 'mt-2' : 'mt-3'} ml-4`}>
            <BulletBlock items={points} />
          </div>
        </>
      )}
      {closing && (
        <p className="mt-6 text-marketing-body-lg text-marketing-text-muted leading-relaxed">
          {closing}
        </p>
      )}
      {optional && (
        <p className="mt-4 text-sm text-marketing-text-subtle leading-relaxed">
          {optional}
        </p>
      )}
      {boundary && (
        <p className="mt-6 text-sm text-marketing-text-subtle leading-relaxed border-l-2 border-marketing-border pl-4">
          {boundary}
        </p>
      )}
    </div>
  );
};
