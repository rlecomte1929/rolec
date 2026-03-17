import React from 'react';
import { PublicHeader } from './PublicHeader';
import { PublicFooter } from './PublicFooter';
import { BackToTop } from './BackToTop';

interface PublicLayoutProps {
  children: React.ReactNode;
  /** Max width of main content: 'default' (72rem) | 'narrow' (48rem) | 'wide' (80rem) | 'full' */
  maxWidth?: 'default' | 'narrow' | 'wide' | 'full';
  /** Remove top/bottom padding for full-bleed sections */
  noPadding?: boolean;
  /** Additional class for main */
  mainClassName?: string;
}

export const PublicLayout: React.FC<PublicLayoutProps> = ({
  children,
  maxWidth = 'default',
  noPadding = false,
  mainClassName = '',
}) => {
  const containerWidth =
    maxWidth === 'narrow'
      ? 'max-w-marketing-narrow'
      : maxWidth === 'wide'
        ? 'max-w-marketing-wide'
        : maxWidth === 'full'
          ? 'max-w-full'
          : 'max-w-marketing';

  return (
    <div className="min-h-screen flex flex-col bg-marketing-surface-subtle text-marketing-text">
      <PublicHeader />
      <main
        className={`flex-1 w-full min-w-0 ${noPadding ? '' : 'pt-6 sm:pt-8 md:pt-10 pb-12 sm:pb-16 md:pb-20'} ${mainClassName}`}
      >
        <div
          className={`mx-auto w-full max-w-full px-4 sm:px-6 lg:px-8 ${containerWidth} ${
            noPadding ? '' : 'py-0'
          }`}
        >
          {children}
        </div>
      </main>
      <PublicFooter />
      <BackToTop />
    </div>
  );
};
